"""Cluster connectivity as observed by KubeMedic. Read-only."""

from fastapi import APIRouter, Request

from app.investigation.models import ClusterStatus

router = APIRouter()


@router.get("/api/v1/cluster/status", response_model=ClusterStatus)
def cluster_status(request: Request) -> ClusterStatus:
    return request.app.state.cluster.status()
