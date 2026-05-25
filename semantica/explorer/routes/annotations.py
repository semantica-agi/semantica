"""
Annotation routes — CRUD for collaborative annotations on graph nodes.

Annotations are stored in-memory on the ``GraphSession`` and do not
modify Semantica core.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_session
from ..schemas import AnnotationCreate, AnnotationResponse
from ..session import GraphSession

router = APIRouter(prefix="/api/annotations", tags=["Annotations"])


@router.get("", response_model=list[AnnotationResponse])
async def list_annotations(
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    session: GraphSession = Depends(get_session),
):
    """List annotations, optionally filtered by node_id."""
    anns = await asyncio.to_thread(session.get_annotations, node_id)
    return [AnnotationResponse(**a) for a in anns]


@router.post("", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    body: AnnotationCreate,
    session: GraphSession = Depends(get_session),
):
    """Create a new annotation on a node."""
    node = await asyncio.to_thread(session.get_node, body.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{body.node_id}' not found")

    ann_data = body.model_dump()
    ann_id = await asyncio.to_thread(session.add_annotation, ann_data)

    stored = await asyncio.to_thread(session.get_annotation, ann_id)
    if stored is not None:
        return AnnotationResponse(**stored)

    return AnnotationResponse(
        annotation_id=ann_id,
        node_id=body.node_id,
        content=body.content,
        tags=body.tags,
        visibility=body.visibility,
    )


@router.delete("/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: str,
    session: GraphSession = Depends(get_session),
):
    """Delete an annotation by ID."""
    deleted = await asyncio.to_thread(session.delete_annotation, annotation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Annotation '{annotation_id}' not found")
    return None
