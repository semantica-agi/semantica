# -*- coding: utf-8 -*-
"""TextEmbedder 三表征扩展测试（PRD-0004 #32，fork 基元）。

全程 stub BGEM3FlagModel（monkeypatch 类符号 + 可用性旗标）：
不加载真权重、不在线下载；验证接口契约（dense 兼容 / 三表征输出 /
维度探针 / 后端不可用时的显式错误）。
"""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from semantica.embeddings import text_embedder as te_mod
from semantica.embeddings.text_embedder import TextEmbedder
from semantica.utils.exceptions import ProcessingError


def _fake_flag_model(dense_dim=8, n_tokens=5):
    """BGEM3FlagModel 替身：encode 按开关返回三表征。"""
    model = MagicMock()

    def encode(texts, return_dense=True, return_sparse=False, return_colbert_vecs=False):
        n = len(list(texts))
        out = {}
        if return_dense:
            out["dense_vecs"] = np.ones((n, dense_dim), dtype=np.float32) / dense_dim
        if return_sparse:
            out["lexical_weights"] = [{100 + i: 0.5} for i in range(n)]
        if return_colbert_vecs:
            out["colbert_vecs"] = [
                np.ones((n_tokens, dense_dim), dtype=np.float32) for _ in range(n)
            ]
        return out

    model.encode.side_effect = encode
    return model


class TriEmbedderTestBase(unittest.TestCase):
    def setUp(self):
        self.flag_patcher = patch.object(te_mod, "BGEM3FlagModel", autospec=True)
        self.flag_cls = self.flag_patcher.start()
        self.flag_cls.return_value = _fake_flag_model()
        self.avail_patcher = patch.object(te_mod, "FLAGEMBEDDING_AVAILABLE", True)
        self.avail_patcher.start()

    def tearDown(self):
        self.flag_patcher.stop()
        self.avail_patcher.stop()


class TestTextEmbedderTri(TriEmbedderTestBase):
    def test_init_flagembedding_probes_dimension(self):
        """flagembedding 后端加载 + 维度探针（微型 dense 前向）。"""
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding", device="cpu")
        self.assertEqual(emb.get_method(), "flagembedding")
        self.assertTrue(emb.supports_tri_representation)
        self.assertEqual(emb.embedding_dimension, 8)  # 探针值（fake dense 8 维）

    def test_dense_interface_unchanged(self):
        """dense 接口向后兼容：embed_text/embed_batch 返回稠密向量，签名与语义不变。"""
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        v = emb.embed_text("血虚证 头晕心悸")
        self.assertEqual(v.shape, (8,))
        mat = emb.embed_batch(["四物汤", "六味地黄丸"])
        self.assertEqual(mat.shape, (2, 8))

    def test_embed_text_tri_contract(self):
        """三表征契约：dense 向量 / sparse 词权重 dict / colbert token 矩阵。"""
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        tri = emb.embed_text_tri("血虚证 头晕心悸")
        self.assertEqual(set(tri), {"dense", "sparse", "colbert"})
        self.assertEqual(tri["dense"].shape, (8,))
        self.assertIsInstance(tri["sparse"], dict)  # {token_id: weight}
        self.assertEqual(tri["colbert"].shape, (5, 8))  # (n_tokens, dim)

    def test_embed_batch_tri_contract(self):
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        tri = emb.embed_batch_tri(["四物汤", "六味地黄丸"])
        self.assertEqual(tri["dense"].shape, (2, 8))
        self.assertEqual(len(tri["sparse"]), 2)
        self.assertEqual(len(tri["colbert"]), 2)
        self.assertEqual(tri["colbert"][0].shape, (5, 8))

    def test_encode_once_per_batch(self):
        """一次前向产三表征（不是 dense/sparse/colbert 各跑一遍）。"""
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        emb.embed_batch_tri(["a", "b"])
        call = emb.flag_model.encode.call_args
        self.assertTrue(call.kwargs.get("return_dense") and call.kwargs.get("return_sparse")
                        and call.kwargs.get("return_colbert_vecs"))

    def test_tri_on_non_flag_backend_raises(self):
        """非 flag 后端请求三表征 → 显式 ProcessingError（不静默给伪三表征）。"""
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        emb.flag_model = None  # 模拟后端退化为 fallback
        with self.assertRaises(ProcessingError):
            emb.embed_text_tri("x")
        self.assertFalse(emb.supports_tri_representation)

    def test_tri_empty_text_raises(self):
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        with self.assertRaises(ProcessingError):
            emb.embed_text_tri("  ")
        with self.assertRaises(ProcessingError):
            emb.embed_batch_tri([])

    def test_flag_model_load_failure_degrades_to_fallback(self):
        """权重加载失败 → 退 fallback（调用方 get_method 自检拦住，附录 A 口径）。"""
        self.flag_cls.side_effect = RuntimeError("weights not found")
        emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        self.assertEqual(emb.get_method(), "fallback")
        self.assertFalse(emb.supports_tri_representation)

    def test_flagembedding_unavailable_warns_and_falls_back(self):
        with patch.object(te_mod, "FLAGEMBEDDING_AVAILABLE", False):
            emb = TextEmbedder(model_name="BAAI/bge-m3", method="flagembedding")
        self.assertEqual(emb.get_method(), "fallback")

    def test_sentence_transformers_path_unaffected(self):
        """既有 sentence_transformers 后端不回归（flag 分支不侵入旧路径）。"""
        with patch.object(te_mod, "SentenceTransformer") as st_cls, \
                patch.object(te_mod, "SENTENCE_TRANSFORMERS_AVAILABLE", True):
            st_cls.return_value.get_sentence_embedding_dimension.return_value = 8
            emb = TextEmbedder(model_name="x", method="sentence_transformers")
        self.assertEqual(emb.get_method(), "sentence_transformers")
        self.assertFalse(emb.supports_tri_representation)


if __name__ == "__main__":
    unittest.main()
