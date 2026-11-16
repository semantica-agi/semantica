"""Semantica.build_knowledge_base can be called more than once (#2218)."""

from semantica.core import Semantica


def test_build_knowledge_base_twice_on_one_instance(tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("Dr. Arjun Rao is a pediatrician in Mysuru.", encoding="utf-8")
    framework = Semantica()

    first = framework.build_knowledge_base(sources=[str(note)], embeddings=False)
    second = framework.build_knowledge_base(sources=[str(note)], embeddings=False)

    assert first["statistics"]["sources_processed"] == 1
    assert second["statistics"]["sources_processed"] == 1


def test_registered_step_handlers_are_kept(tmp_path):
    framework = Semantica()
    calls = []

    def handler(data, **config):
        calls.append(data)
        return data

    framework.pipeline_builder.register_step_handler("default", handler)
    note = tmp_path / "note.txt"
    note.write_text("text", encoding="utf-8")

    framework.build_knowledge_base(sources=[str(note)], embeddings=False)
    framework.build_knowledge_base(sources=[str(note)], embeddings=False)

    assert len(calls) == 2
