import pytest

from semantica.kg import CommunityDetector


@pytest.mark.parametrize("chunk_size", [0, -1, None, 1.5, True])
def test_label_propagation_rejects_invalid_chunk_size(chunk_size):
    graph = {
        "nodes": [{"id": str(i)} for i in range(4)],
        "edges": [{"source": "0", "target": "1"}],
    }

    with pytest.raises(
        ValueError, match="chunk_size must be an integer at least 1"
    ):
        CommunityDetector().detect_communities(
            graph,
            algorithm="label_propagation",
            chunk_size=chunk_size,
        )
