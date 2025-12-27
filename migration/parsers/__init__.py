"""Модульные парсеры для универсального импортера."""

from .base import BaseParser, ParseContext
from .photo import PhotoParser
from .facts import FactsParser
from .tags import TagsParser
from .social import SocialLinksParser
from .text import TextBlockParser
from .timeline import TimelineParser
from .members import TeamMembersParser
from .gallery import GalleryParser
from .rating import RatingParser

__all__ = [
    'BaseParser',
    'ParseContext',
    'PhotoParser',
    'FactsParser',
    'TagsParser',
    'SocialLinksParser',
    'TextBlockParser',
    'TimelineParser',
    'TeamMembersParser',
    'GalleryParser',
    'RatingParser',
]
