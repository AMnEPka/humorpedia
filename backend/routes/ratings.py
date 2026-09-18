"""Public anonymous rating endpoints."""

import os

from fastapi import APIRouter, Request, Response

from models.rating import RatingEntityType, RatingResponse, RatingVoteRequest
from services.ratings import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    create_voter_cookie,
    get_rating_snapshot,
    set_rating,
    verify_voter_cookie,
    visitor_hash,
)
from utils.database import get_db
from utils.rate_limit import limiter


router = APIRouter(prefix="/ratings", tags=["ratings"])


def _set_private_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"


def _get_visitor(request: Request, response: Response) -> str:
    cookie_value = request.cookies.get(COOKIE_NAME)
    token = verify_voter_cookie(cookie_value)
    if token is None:
        cookie_value = create_voter_cookie()
        token = verify_voter_cookie(cookie_value)
        response.set_cookie(
            COOKIE_NAME,
            cookie_value,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            secure=os.environ.get("ENVIRONMENT") == "production",
            samesite="lax",
            path="/api/ratings",
        )
    return visitor_hash(token)


@router.get("/{entity_type}/{entity_id}", response_model=RatingResponse)
async def get_rating(
    entity_type: RatingEntityType,
    entity_id: str,
    request: Request,
    response: Response,
):
    _set_private_headers(response)
    voter = _get_visitor(request, response)
    return await get_rating_snapshot(await get_db(), entity_type.value, entity_id, voter)


@router.put("/{entity_type}/{entity_id}", response_model=RatingResponse)
@limiter.limit("10/minute")
async def put_rating(
    entity_type: RatingEntityType,
    entity_id: str,
    data: RatingVoteRequest,
    request: Request,
    response: Response,
):
    _set_private_headers(response)
    voter = _get_visitor(request, response)
    return await set_rating(await get_db(), entity_type.value, entity_id, voter, data.score)
