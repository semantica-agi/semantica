# -*- coding: utf-8 -*-
"""TextReranker 重排基元测试（PRD-0004 #34，fork 基元）。

mock FlagReranker / CrossEncoder：不加载真权重；验证输入输出契约、
后端选择、显式失败（不静默换后端、不静默给伪分数）。
"""

import unittest
from unittest.mock import MagicMock, patch

from semantica.embeddings import text_reranker as tr_mod
from semantica.embeddings.text_reranker import TextReranker
from semantica.utils.exceptions import ProcessingError


class TestTextReranker(unittest.TestCase):
    def setUp(self):
        self.flag_patcher = patch.object(tr_mod, "FlagReranker", autospec=True)
        self.flag_cls = self.flag_patcher.start()
        self.flag_model = MagicMock()
        self.flag_model.compute_score.return_value = [0.9, 0.1, 0.5]
        self.flag_cls.return_value = self.flag_model
        self.flag_avail = patch.object(tr_mod, "FLAGRERANKER_AVAILABLE", True)
        self.flag_avail.start()

    def tearDown(self):
        self.flag_patcher.stop()
        self.flag_avail.stop()

    def test_default_method_is_flagembedding(self):
        """默认后端 FlagReranker（Phase 0 初判：第一方运行时）。"""
        rr = TextReranker(model_name="BAAI/bge-reranker-v2-m3")
        self.assertEqual(rr.get_method(), "flagembedding")
        self.assertTrue(rr.get_model_info()["model_loaded"])

    def test_rerank_scores_aligned_with_documents(self):
        """分数与文档列表对齐（query-doc 对顺序拼接）。"""
        rr = TextReranker()
        docs = ["四物汤主治血虚", "六味地黄丸主治肾阴虚", "补中益气汤主治气虚"]
        scores = rr.rerank("血虚证 头晕心悸", docs)
        self.assertEqual(scores, [0.9, 0.1, 0.5])
        pairs = self.flag_model.compute_score.call_args.args[0]
        self.assertEqual(pairs[0], ["血虚证 头晕心悸", "四物汤主治血虚"])

    def test_rerank_empty_documents(self):
        rr = TextReranker()
        self.assertEqual(rr.rerank("q", []), [])

    def test_rerank_empty_query_raises(self):
        rr = TextReranker()
        with self.assertRaises(ProcessingError):
            rr.rerank("  ", ["d"])

    def test_model_unavailable_raises_not_fake_scores(self):
        """模型未加载 → rerank 显式抛错（调用方决定降级），绝不返回伪分数。"""
        rr = TextReranker()
        rr.model = None
        rr._load_error = "weights not found"
        with self.assertRaises(ProcessingError):
            rr.rerank("q", ["d"])
        self.assertEqual(rr.get_method(), "unavailable")

    def test_backend_load_failure_keeps_error_no_cross_fallback(self):
        """指定后端加载失败不静默换另一后端（降级决策在调用方）。"""
        self.flag_cls.side_effect = RuntimeError("offline weight missing")
        rr = TextReranker()
        self.assertIsNone(rr.model)
        self.assertIn("offline weight missing", rr._load_error)
        with patch.object(tr_mod, "CROSSENCODER_AVAILABLE", True), \
                patch.object(tr_mod, "CrossEncoder") as ce_cls:
            TextReranker()
            ce_cls.assert_not_called()  # 不跨界 fallback

    def test_sentence_transformers_backend(self):
        with patch.object(tr_mod, "CROSSENCODER_AVAILABLE", True), \
                patch.object(tr_mod, "CrossEncoder") as ce_cls:
            import numpy as np
            ce_cls.return_value.predict.return_value = np.array([2.0, -1.0])
            rr = TextReranker(method="sentence_transformers")
            scores = rr.rerank("q", ["a", "b"])
        self.assertEqual(scores, [2.0, -1.0])  # CrossEncoder 原始 logits
        self.assertEqual(rr.get_method(), "sentence_transformers")

    def test_unknown_method_rejected(self):
        with self.assertRaises(ProcessingError):
            TextReranker(method="bm25")


if __name__ == "__main__":
    unittest.main()
