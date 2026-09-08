from pathlib import Path
from unittest.mock import patch
import pytest

from semantica.parse.docx_parser import DOCXParser
from semantica.parse.excel_parser import ExcelParser
from semantica.parse.html_parser import HTMLParser
from semantica.parse.xml_parser import XMLParser
from semantica.utils.exceptions import ProcessingError


def _load_toml(file_path: Path) -> dict:
    """Load and parse a TOML file across Python 3.8-3.14+ without mode mismatches."""
    content = file_path.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+ standard library

        return tomllib.loads(content)
    except ImportError:
        try:
            import tomli  # Fast PEP 680 compatible parser for Python < 3.11

            return tomli.loads(content)
        except ImportError:
            import toml  # Fallback toml parser

            return toml.loads(content)


def test_core_dependencies_count():
    """pyproject.toml must contain exactly 22 unique core dependencies."""
    repo_root = Path(__file__).resolve().parents[1]
    data = _load_toml(repo_root / "pyproject.toml")
    deps = data["project"]["dependencies"]
    normalized_names = {
        d.split(";")[0].split(">=")[0].split("<")[0].split("==")[0].strip()
        for d in deps
    }
    expected_22 = {
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "rdflib",
        "networkx",
        "requests",
        "chardet",
        "protobuf",
        "grpcio",
        "pillow",
        "pydantic",
        "click",
        "rich",
        "tqdm",
        "pyyaml",
        "toml",
        "python-dotenv",
        "loguru",
        "structlog",
        "httpx",
        "pyarrow",
    }
    assert normalized_names == expected_22
    assert len(normalized_names) == 22


def test_optional_extras_defined():
    """All required optional extras must be declared in pyproject.toml."""
    repo_root = Path(__file__).resolve().parents[1]
    data = _load_toml(repo_root / "pyproject.toml")
    extras = data["project"]["optional-dependencies"]
    for extra in [
        "documents",
        "ingest-git",
        "embeddings-local",
        "nlp-spacy",
        "viz",
        "media",
        "vectorstore-faiss",
        "graph-embeddings",
        "all",
    ]:
        assert extra in extras, f"Missing extra {extra}"
    all_extra_str = str(extras["all"])
    for expected_ref in [
        "documents",
        "ingest-git",
        "embeddings-local",
        "nlp-spacy",
        "viz",
        "media",
        "graph-embeddings",
        "vectorstore-all",
    ]:
        assert expected_ref in all_extra_str, f"Missing {expected_ref} in all"
    # And vectorstore-faiss is in vectorstore-all
    assert "vectorstore-faiss" in str(extras["vectorstore-all"])

    # Verify nlp-spacy does not declare thinc directly (Qodo bot issue 1)
    nlp_spacy_deps = str(extras.get("nlp-spacy", []))
    assert "thinc" not in nlp_spacy_deps, "nlp-spacy should not directly declare thinc"
    assert "spacy" in nlp_spacy_deps, "nlp-spacy must declare spacy"


def test_core_modules_importable():
    """Core modules must be importable without requiring optional extras."""
    import semantica
    import semantica.cli
    import semantica.parse
    import semantica.ingest
    import semantica.embeddings
    import semantica.export
    import semantica.kg
    import semantica.vector_store
    import semantica.visualization
    import semantica.semantic_extract
    import semantica.pipeline

    assert semantica.__version__ is not None


def test_docx_parser_lazy_construction_and_parse_hint():
    with patch("semantica.parse.docx_parser.Document", None):
        parser = DOCXParser()
        assert parser is not None
        with pytest.raises(ProcessingError, match=r"semantica\[documents\]"):
            parser.parse("nonexistent.docx")


def test_excel_parser_lazy_construction_and_parse_hint():
    with patch("semantica.parse.excel_parser.load_workbook", None):
        parser = ExcelParser()
        assert parser is not None
        with pytest.raises(ProcessingError, match=r"semantica\[documents\]"):
            parser.parse("nonexistent.xlsx")


def test_html_parser_lazy_construction_and_parse_hint():
    with patch("semantica.parse.html_parser.BeautifulSoup", None):
        parser = HTMLParser()
        assert parser is not None
        with pytest.raises(ProcessingError, match=r"semantica\[documents\]"):
            parser.parse("nonexistent.html")


def test_xml_parser_etree_fallback():
    with patch("semantica.parse.xml_parser.etree", None):
        parser = XMLParser()
        assert parser is not None
        result = parser.parse("<root><item id='1'>Test</item></root>")
        assert result is not None
        assert result.root is not None
        assert result.root.tag == "root"


def test_xml_parser_lxml_explicit_requires_documents_extra():
    with patch("semantica.parse.xml_parser.etree", None):
        parser = XMLParser(engine="lxml")
        assert parser is not None
        with pytest.raises(ProcessingError, match=r"semantica\[documents\]"):
            parser.parse("<root/>")


def test_xml_ingestor_missing_hint():
    with patch("semantica.ingest.xml_ingestor.etree", None):
        from semantica.ingest.xml_ingestor import XMLIngestor

        with pytest.raises(ImportError, match=r"semantica\[documents\]"):
            XMLIngestor()


def test_xml_ingestor_package_import_missing_hint():
    import semantica.ingest as ingest_mod

    ingest_mod.__dict__.pop("XMLIngestor", None)
    with patch("semantica.ingest.xml_ingestor.etree", None):
        with pytest.raises(ImportError, match=r"semantica\[documents\]"):
            _ = ingest_mod.XMLIngestor


def test_repo_ingestor_missing_hint():
    with patch("semantica.ingest.repo_ingestor.git", None):
        from semantica.ingest.repo_ingestor import RepoIngestor

        with pytest.raises(ImportError, match=r"semantica\[ingest-git\]"):
            RepoIngestor()


def test_repo_ingestor_package_import_missing_hint():
    import semantica.ingest as ingest_mod

    ingest_mod.__dict__.pop("RepoIngestor", None)
    with patch("semantica.ingest.repo_ingestor.git", None):
        with pytest.raises(ImportError, match=r"semantica\[ingest-git\]"):
            _ = ingest_mod.RepoIngestor


def test_git_analyzer_package_import_succeeds_without_git():
    import semantica.ingest as ingest_mod

    ingest_mod.__dict__.pop("GitAnalyzer", None)
    with patch("semantica.ingest.repo_ingestor.git", None):
        analyzer_cls = ingest_mod.GitAnalyzer
        assert analyzer_cls is not None
        analyzer = analyzer_cls()
        assert analyzer is not None


def test_salesforce_ingestor_package_import_missing_hint():
    import semantica.ingest as ingest_mod

    ingest_mod.__dict__.pop("SalesforceIngestor", None)
    with patch("semantica.ingest.salesforce_ingestor.SALESFORCE_AVAILABLE", False):
        with pytest.raises(ImportError, match=r"semantica\[db-salesforce\]"):
            _ = ingest_mod.SalesforceIngestor


def test_parse_methods_dynamic_default_resolution():
    from semantica.parse.methods import (
        get_parse_method,
        list_available_methods,
        parse_document,
    )

    assert get_parse_method("document", "default") == parse_document
    methods = list_available_methods()
    assert "default" in methods.get("document", [])
    assert "default" in methods.get("structured", [])


def test_node_embedder_gensim_missing_hint():
    with patch("semantica.kg.node_embeddings.GENSIM_AVAILABLE", False):
        from semantica.kg.node_embeddings import NodeEmbedder

        with pytest.raises(ImportError, match=r"semantica\[graph-embeddings\]"):
            NodeEmbedder()


def test_faiss_store_missing_hint():
    with patch("semantica.vector_store.faiss_store.FAISS_AVAILABLE", False):
        from semantica.vector_store.faiss_store import FAISSIndexBuilder, FAISSStore

        builder = FAISSIndexBuilder(128)
        with pytest.raises(ProcessingError, match=r"semantica\[vectorstore-faiss\]"):
            builder.build_index("flat")
        store = FAISSStore(128)
        with pytest.raises(ProcessingError, match=r"semantica\[vectorstore-faiss\]"):
            store.load_index("nonexistent.faiss")


def test_visualization_missing_hint():
    import numpy as np
    from semantica.visualization.embedding_visualizer import EmbeddingVisualizer

    # Plotly is checked via px and go in _check_dependencies
    with patch("semantica.visualization.embedding_visualizer.px", None):
        visualizer = EmbeddingVisualizer()
        with pytest.raises(
            ProcessingError, match=r"Plotly is required.*semantica\[viz\]"
        ):
            visualizer.visualize_2d_projection(np.array([[0.1, 0.2], [0.3, 0.4]]))

    with patch("semantica.visualization.embedding_visualizer.go", None):
        visualizer = EmbeddingVisualizer()
        with pytest.raises(
            ProcessingError, match=r"Plotly is required.*semantica\[viz\]"
        ):
            visualizer.visualize_2d_projection(np.array([[0.1, 0.2], [0.3, 0.4]]))


def test_visualization_umap_missing_hint():
    import numpy as np
    from unittest.mock import MagicMock
    from semantica.visualization.embedding_visualizer import EmbeddingVisualizer

    # Stand in for Plotly so we reach dimensionality reduction
    with patch("semantica.visualization.embedding_visualizer.px", MagicMock()), patch(
        "semantica.visualization.embedding_visualizer.go", MagicMock()
    ), patch("semantica.visualization.embedding_visualizer.umap", None):
        visualizer = EmbeddingVisualizer()
        # High-dimensional embeddings (>2D) trigger dimensionality reduction
        # with method="umap"
        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]])
        with pytest.raises(
            ProcessingError, match=r"UMAP is required.*semantica\[viz\]"
        ):
            visualizer.visualize_2d_projection(embeddings, method="umap")

        # Also verify 3D projection triggers the same actionable error on >3D embeddings
        embeddings_4d = np.array(
            [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]]
        )
        with pytest.raises(
            ProcessingError, match=r"UMAP is required.*semantica\[viz\]"
        ):
            visualizer.visualize_3d_projection(embeddings_4d, method="umap")


def test_visualization_sklearn_missing_hint():
    import numpy as np
    from unittest.mock import MagicMock
    from semantica.visualization.embedding_visualizer import EmbeddingVisualizer

    # Stand in for Plotly so we reach dimensionality reduction
    with patch("semantica.visualization.embedding_visualizer.px", MagicMock()), patch(
        "semantica.visualization.embedding_visualizer.go", MagicMock()
    ):
        visualizer = EmbeddingVisualizer()
        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]])

        # Test direct dependency check
        with patch("semantica.visualization.embedding_visualizer.PCA", None):
            with pytest.raises(ProcessingError, match=r"scikit-learn is required"):
                visualizer._check_dependencies(require_sklearn=True)

        with patch("semantica.visualization.embedding_visualizer.PCA", None):
            with pytest.raises(ProcessingError, match=r"scikit-learn is required"):
                visualizer.visualize_2d_projection(embeddings, method="pca")

        with patch("semantica.visualization.embedding_visualizer.TSNE", None):
            with pytest.raises(ProcessingError, match=r"scikit-learn is required"):
                visualizer.visualize_2d_projection(embeddings, method="tsne")


def test_visualization_options_collision_free():
    """Options like n_components, perplexity must not cause keyword collisions."""
    import numpy as np
    from unittest.mock import MagicMock
    from semantica.visualization.embedding_visualizer import EmbeddingVisualizer

    mock_pca = MagicMock()
    mock_tsne = MagicMock()
    mock_umap_cls = MagicMock()
    mock_umap_module = MagicMock()
    mock_umap_module.UMAP = mock_umap_cls

    with patch("semantica.visualization.embedding_visualizer.PCA", mock_pca), patch(
        "semantica.visualization.embedding_visualizer.TSNE", mock_tsne
    ), patch(
        "semantica.visualization.embedding_visualizer.umap", mock_umap_module
    ), patch(
        "semantica.visualization.embedding_visualizer.px", MagicMock()
    ), patch(
        "semantica.visualization.embedding_visualizer.go", MagicMock()
    ):
        visualizer = EmbeddingVisualizer()
        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]])

        # PCA with n_components
        visualizer.visualize_2d_projection(embeddings, method="pca", n_components=2)
        # TSNE with perplexity and random_state
        visualizer.visualize_2d_projection(
            embeddings, method="tsne", perplexity=1, random_state=42
        )
        # UMAP with n_neighbors and min_dist
        visualizer.visualize_2d_projection(
            embeddings, method="umap", n_neighbors=2, min_dist=0.1
        )
        # 3D with n_components
        visualizer.visualize_3d_projection(embeddings, method="pca", n_components=3)


def test_spacy_load_missing_hint():
    from semantica.semantic_extract.methods import load_spacy_model

    with patch("semantica.semantic_extract.methods.spacy", None):
        with pytest.raises(ImportError, match=r"semantica\[nlp-spacy\]"):
            load_spacy_model("en_core_web_sm")


def test_xml_parser_handles_comments():
    from semantica.parse.xml_parser import etree as real_lxml_etree

    xml_content = (
        "<root><!-- top comment --><item id='1'>Value</item>"
        "<!-- bottom comment --></root>"
    )
    # etree engine (always available in a core-only install)
    p_etree = XMLParser(engine="etree")
    res_etree = p_etree.parse(xml_content)
    assert res_etree.root.tag == "root"
    assert len(res_etree.root.children) == 1
    assert res_etree.root.children[0].tag == "item"
    assert res_etree.root.children[0].text == "Value"

    # lxml engine (only meaningful when the 'documents' extra is installed)
    if real_lxml_etree is None:
        pytest.skip("lxml not installed (requires semantica[documents])")
    p_lxml = XMLParser(engine="lxml")
    res_lxml = p_lxml.parse(xml_content)
    assert res_lxml.root.tag == "root"
    assert len(res_lxml.root.children) == 1
    assert res_lxml.root.children[0].tag == "item"
    assert res_lxml.root.children[0].text == "Value"


def test_public_api_ingestor_handles_xml_comments():
    from semantica.ingest.public_api_ingestor import (
        PublicAPIIngestor,
        lxml_etree as real_lxml_etree,
        safe_xml_etree as real_safe_xml_etree,
    )

    if real_lxml_etree is None and real_safe_xml_etree is None:
        pytest.skip("neither defusedxml nor lxml installed (requires semantica[documents]/[explorer])")

    xml_content = "<root><!-- comment --><item id='1'>Value</item></root>"
    ingestor = PublicAPIIngestor(rate_limit_delay=0)

    # 1. Default (defusedxml if available)
    parsed = ingestor._parse_xml(xml_content)
    assert parsed["tag"] == "root"
    assert len(parsed["children"]) == 1
    assert parsed["children"][0]["tag"] == "item"
    assert parsed["children"][0]["text"] == "Value"

    # 2. lxml fallback (only meaningful when lxml is actually installed)
    if real_lxml_etree is None:
        pytest.skip("lxml not installed (requires semantica[documents])")
    with patch("semantica.ingest.public_api_ingestor.safe_xml_etree", None):
        parsed_lxml = ingestor._parse_xml(xml_content)
        assert parsed_lxml["tag"] == "root"
        assert len(parsed_lxml["children"]) == 1
        assert parsed_lxml["children"][0]["tag"] == "item"
        assert parsed_lxml["children"][0]["text"] == "Value"


def test_huggingface_model_loader_catches_oserror():
    import builtins
    from unittest.mock import MagicMock
    from semantica.semantic_extract.providers import HuggingFaceModelLoader

    mock_torch = MagicMock()
    mock_torch.Tensor = type("Tensor", (), {})
    with patch.dict("sys.modules", {"torch": mock_torch}):
        loader = HuggingFaceModelLoader()
        # 1. Test ModuleNotFoundError / ImportError
        with patch.dict("sys.modules", {"transformers": None}):
            with pytest.raises(ImportError, match=r"semantica\[models-huggingface\]"):
                loader.load_ner_model("bert-base-cased")

            with pytest.raises(ImportError, match=r"semantica\[models-huggingface\]"):
                loader.load_relation_model("bert-base-cased")

            with pytest.raises(ImportError, match=r"semantica\[models-huggingface\]"):
                loader.load_triplet_model("t5-base")

        # 2. Test OSError (e.g. corrupt DLL / missing shared library)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "transformers":
                raise OSError("DLL load failed")
            return real_import(name, *args, **kwargs)

        try:
            builtins.__import__ = fake_import
            with pytest.raises(ImportError, match=r"semantica\[models-huggingface\]"):
                loader.load_ner_model("bert-base-cased-oserror")

            with pytest.raises(ImportError, match=r"semantica\[models-huggingface\]"):
                loader.load_relation_model("bert-base-cased-oserror")

            with pytest.raises(ImportError, match=r"semantica\[models-huggingface\]"):
                loader.load_triplet_model("t5-base-oserror")
        finally:
            builtins.__import__ = real_import
