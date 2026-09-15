# -*- coding: utf-8 -*-
"""MilvusStore 三向量字段基元测试（PRD-0004 #32，fork 基元）。

mock MilvusClient（记录调用），schema/索引用真实 pymilvus 3.x 类组装
（离线可组装，Phase 0 已核验）；验证 schema 结构、写入负载形态、
逐腿检索调用形态与命中归一化。旧单稠密签名向后兼容不破。
"""

import unittest
from unittest.mock import MagicMock

import numpy as np

from semantica.vector_store import milvus_store as ms


class FakeMilvusClient:
    """pymilvus MilvusClient 替身：记录 create/insert/search/drop 调用。"""

    def __init__(self, hits=None, has=False):
        self.created = {}
        self.inserted = {}
        self._insert_batches = []
        self.searches = []
        self.dropped = []
        self._hits = hits or []
        self._has = has

    def create_collection(self, collection_name, schema=None, index_params=None):
        self.created[collection_name] = (schema, index_params)

    def insert(self, collection_name, data):
        self.inserted.setdefault(collection_name, []).extend(data)
        self._insert_batches.append(list(data))
        return {"insert_count": len(data)}

    def search(self, collection_name, data, anns_field=None, search_params=None,
               limit=None, output_fields=None):
        self.searches.append({
            "collection": collection_name, "data": data, "anns_field": anns_field,
            "search_params": search_params, "limit": limit, "output_fields": output_fields,
        })
        return [list(self._hits)]

    def has_collection(self, collection_name):
        return self._has

    def drop_collection(self, collection_name):
        self.dropped.append(collection_name)


HITS = [
    {"id": 7, "distance": 0.9, "entity": {"metadata": {"book": "药典", "page": 12}}},
    {"id": 3, "distance": 0.5, "entity": {"metadata": {"book": "本草", "page": 3}}},
]


class TestTriCollectionPrimitives(unittest.TestCase):
    def test_create_tri_collection_schema(self):
        """三向量字段一次建齐：fields + struct_fields（tokens）+ metadata。"""
        client = FakeMilvusClient()
        schema = ms.create_tri_collection(client, "tcm_chunks_b1", dimension=1024)
        names = [f.name for f in schema.fields]
        self.assertEqual(names, ["id", "vector", "sparse", "metadata"])
        struct_names = [f.name for f in schema._struct_fields]
        self.assertEqual(struct_names, ["tokens"])  # StructArray 字段在独立列表（Phase 0 取证）
        # 序列化完整性（create_collection 走 to_dict 路径）
        d = schema.to_dict()
        self.assertEqual([f["name"] for f in d["struct_fields"]], ["tokens"])
        self.assertIn("tcm_chunks_b1", client.created)

    def test_create_tri_collection_indexes(self):
        """索引三路：dense IVF_FLAT COSINE / sparse SPARSE_INVERTED IP / tokens[emb] MAX_SIM_COSINE。"""
        client = FakeMilvusClient()
        ms.create_tri_collection(client, "c", dimension=8)
        _, index_params = client.created["c"]
        # IndexParams 为列表容器；IndexParam 私有属性是唯一内省面（跨版本 tripwire）
        indexes = {i._field_name: {"index_type": i._index_type, **i._configs}
                   for i in index_params}
        self.assertEqual(set(indexes), {"vector", "sparse", "tokens[emb]"})
        self.assertEqual(indexes["vector"]["metric_type"], "COSINE")
        self.assertEqual(indexes["vector"]["index_type"], "IVF_FLAT")
        self.assertEqual(indexes["sparse"]["index_type"], "SPARSE_INVERTED_INDEX")
        self.assertEqual(indexes["sparse"]["metric_type"], "IP")
        self.assertEqual(indexes["tokens[emb]"]["metric_type"], "MAX_SIM_COSINE")

    def test_insert_tri_vectors_payload(self):
        """行式 dict 负载：sparse dict 透传、colbert→[{emb:[…]}]、metadata/ids 对齐。"""
        client = FakeMilvusClient()
        dense = [np.ones(8, dtype=np.float32), np.zeros(8, dtype=np.float32)]
        sparse = [{10: 0.5}, None]  # 第二行缺稀疏 → 空 dict 占位
        colbert = [np.ones((3, 8), dtype=np.float32), None]  # 缺 colbert → 空数组占位（回补路径）
        ids = ms.insert_tri_vectors(
            client, "c", dense, sparse, colbert,
            metadata=[{"book": "药典", "page": 1}, {"book": "本草", "page": 2}],
            ids=["a", "b"],
        )
        rows = client.inserted["c"]
        self.assertEqual(ids, ["a", "b"])
        self.assertEqual([r["id"] for r in rows], ["a", "b"])
        self.assertEqual(rows[0]["sparse"], {10: 0.5})
        self.assertEqual(rows[1]["sparse"], {})
        self.assertEqual(len(rows[0]["tokens"]), 3)
        self.assertEqual(rows[0]["tokens"][0]["emb"], [1.0] * 8)
        self.assertEqual(rows[1]["tokens"], [])
        self.assertEqual(rows[0]["metadata"]["book"], "药典")

    def test_insert_length_mismatch_raises(self):
        client = FakeMilvusClient()
        with self.assertRaises(Exception):
            ms.insert_tri_vectors(client, "c", [np.ones(8)], [{}, {}], [None, None])

    def test_insert_split_into_batches_on_size_limit(self):
        """大负载按 max_batch_bytes 分批（ColBERT 重行），行序与 id 全保留。

        生产取证：593 行一次 insert 的 gRPC 消息 888MB 超 64MiB 上限被拒
        （RESOURCE_EXHAUSTED），基元必须切块；分批后每次调用独立可成功。
        """
        client = FakeMilvusClient()
        n = 300
        dense = [np.ones(128, dtype=np.float32) for _ in range(n)]
        sparse = [{i: 0.1} for i in range(n)]
        colbert = [np.ones((4000, 4), dtype=np.float32) for _ in range(n)]  # ~40KB/行
        ids = ms.insert_tri_vectors(
            client, "c", dense, sparse, colbert,
            metadata=[{"book": "药典"} for _ in range(n)],
            ids=[f"r{i}" for i in range(n)],
            max_batch_bytes=512 * 1024,
        )
        self.assertGreater(len(client._insert_batches), 1)
        self.assertEqual(sum(len(b) for b in client._insert_batches), n)
        self.assertTrue(all(len(b) <= 16 for b in client._insert_batches))
        self.assertEqual(ids, [f"r{i}" for i in range(n)])
        # 行内结构不受分批影响（分批只切 insert 调用）
        rows = client.inserted["c"]
        self.assertEqual(rows[0]["sparse"], {0: 0.1})
        self.assertEqual(rows[0]["tokens"][0]["emb"], [1.0] * 4)

    def test_drop_collection_if_exists_idempotent(self):
        gone = FakeMilvusClient(has=True)
        self.assertTrue(ms.drop_collection_if_exists(gone, "c"))
        self.assertEqual(gone.dropped, ["c"])
        absent = FakeMilvusClient(has=False)
        self.assertFalse(ms.drop_collection_if_exists(absent, "c"))


class TestTriLegSearch(unittest.TestCase):
    def test_dense_leg_call_shape(self):
        client = FakeMilvusClient(hits=HITS)
        out = ms.search_tri_leg(client, "c", "dense", np.ones(8) * 0.1, top_k=6)
        call = client.searches[0]
        self.assertEqual(call["anns_field"], "vector")
        self.assertEqual(call["search_params"]["metric_type"], "COSINE")
        self.assertEqual(call["limit"], 6)
        self.assertEqual(len(call["data"][0]), 8)
        self.assertEqual([h["id"] for h in out], [7, 3])
        self.assertEqual(out[0]["score"], 0.9)
        self.assertEqual(out[0]["metadata"]["book"], "药典")

    def test_sparse_leg_call_shape(self):
        client = FakeMilvusClient(hits=HITS)
        ms.search_tri_leg(client, "c", "sparse", {100: 0.4, 200: 0.6}, top_k=6)
        call = client.searches[0]
        self.assertEqual(call["anns_field"], "sparse")
        self.assertEqual(call["search_params"]["metric_type"], "IP")
        self.assertEqual(call["data"], [{100: 0.4, 200: 0.6}])

    def test_colbert_leg_builds_embedding_list(self):
        """colbert 腿：token 矩阵自动包成 EmbeddingList，anns_field=tokens[emb]。"""
        client = FakeMilvusClient(hits=HITS)
        ms.search_tri_leg(client, "c", "colbert", np.ones((5, 8), dtype=np.float32), top_k=4)
        call = client.searches[0]
        self.assertEqual(call["anns_field"], "tokens[emb]")
        self.assertEqual(call["search_params"]["metric_type"], "MAX_SIM_COSINE")
        from pymilvus.client.embedding_list import EmbeddingList

        self.assertIsInstance(call["data"][0], EmbeddingList)
        self.assertEqual(call["data"][0].shape, (5, 8))

    def test_unknown_leg_raises(self):
        client = FakeMilvusClient()
        with self.assertRaises(Exception):
            ms.search_tri_leg(client, "c", "bm25", {})


class TestMilvusStoreTriWrapper(unittest.TestCase):
    def _store(self):
        store = ms.MilvusStore.__new__(ms.MilvusStore)
        store.host, store.port = "milvus", 19530
        store.logger = MagicMock()
        store._tri_client = FakeMilvusClient(hits=HITS)
        return store

    def test_wrapper_delegates_and_builds_client_uri(self):
        store = self._store()
        schema = store.create_tri_collection("c", dimension=8)
        self.assertIn("c", store._tri_client.created)
        self.assertIsNotNone(schema)
        store.insert_tri_vectors([np.ones(8)], [{}], [np.ones((2, 8), dtype=np.float32)],
                                 collection_name="c", metadata=[{"k": 1}])
        self.assertEqual(len(store._tri_client.inserted["c"]), 1)
        hits = store.search_tri_leg("c", "dense", np.ones(8))
        self.assertEqual(hits[0]["id"], 7)
        store.drop_collection("c")

    def test_pymilvus_client_uri(self):
        """懒建 MilvusClient 的 uri 形态 http://host:port（无 scheme 会被当 milvus-lite）。"""
        store = self._store()
        captured = {}

        class _Cap:
            def __init__(self, uri=None):
                captured["uri"] = uri

        import pymilvus
        orig = pymilvus.MilvusClient
        pymilvus.MilvusClient = _Cap
        try:
            store._tri_client = None
            store._pymilvus_client()
        finally:
            pymilvus.MilvusClient = orig
        self.assertEqual(captured["uri"], "http://milvus:19530")

    def test_legacy_create_collection_signature_untouched(self):
        """旧单稠密路径签名/行为不变（向后兼容基线）。"""
        source = open(ms.__file__, encoding="utf-8").read()
        self.assertIn("def create_collection(", source)
        self.assertIn('FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension)', source)


if __name__ == "__main__":
    unittest.main()
