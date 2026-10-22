"""Measured query bounds on a disposable MongoDB: PERFORMANCE_INTEGRATION=1."""
import asyncio
from copy import deepcopy
import os
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
import pytest

from routes.content_teams import _season_team_refs_query
from services.competitions import create_competition_indexes


@pytest.mark.skipif(os.environ.get('PERFORMANCE_INTEGRATION') != '1', reason='Needs own MongoDB with PERFORMANCE_INTEGRATION=1')
def test_team_slug_reference_lookup_scales_with_matching_seasons():
    async def check():
        client = AsyncIOMotorClient(os.environ['MONGO_URL'])
        name = 'humorpedia_perf_test_' + uuid.uuid4().hex
        db = client[name]
        assert db.name == name and not await db.list_collection_names()
        try:
            matches = [
                {'_id': 'match-0', 'teams': [{'team_id': 'target', 'slug': 'old-slug'}]},
                {'_id': 'match-1', 'winners': [{'slug': 'old-slug'}]},
                {'_id': 'match-2', 'stages': [{'games': [{'results': [{'team_id': 'target'}]}]}]},
            ]
            await db.seasons.insert_many(deepcopy(matches))
            await db.seasons.insert_many([
                {'_id': f'unrelated-{n}', 'teams': [{'team_id': f'other-{n}', 'slug': f'other-{n}'}]}
                for n in range(500)
            ])

            async def ensure(collection, keys, **options):
                await collection.create_index(keys, **options)

            await create_competition_indexes(ensure, db)
            query = _season_team_refs_query('target', 'old-slug')
            for extra in (0, 3000):
                if extra:
                    await db.seasons.insert_many([
                        {'_id': f'extra-{n}', 'stages': [{'games': [{'results': [{'team_id': f'other-extra-{n}'}]}]}]}
                        for n in range(extra)
                    ])
                explained = await db.command({'explain': {'find': 'seasons', 'filter': query}, 'verbosity': 'executionStats'})
                stats = explained['executionStats']
                assert stats['nReturned'] == 3
                assert stats['totalDocsExamined'] <= 3
                actual = await db.seasons.find(query).sort('_id', 1).to_list(None)
                assert actual == matches
        finally:
            assert db.name == name and name.startswith('humorpedia_perf_test_')
            await client.drop_database(name)
            client.close()

    asyncio.run(check())



@pytest.mark.skipif(os.environ.get('PERFORMANCE_INTEGRATION') != '1', reason='Needs own MongoDB with PERFORMANCE_INTEGRATION=1')
def test_recommendation_sort_index_preserves_candidate_pool_and_daily_results():
    from services import recommendations

    async def check():
        client = AsyncIOMotorClient(os.environ['MONGO_URL'])
        name = 'humorpedia_perf_test_' + uuid.uuid4().hex
        db = client[name]
        assert not await db.list_collection_names()
        try:
            await db.people.insert_many([
                {'_id': f'person-{n:04}', 'slug': f'person-{n:04}', 'title': f'Person {n}',
                 'tags': ['shared'], 'featured': n % 3 == 0, 'views': n % 7,
                 'status': 'archived' if n % 50 == 0 else 'published'}
                for n in range(500)
            ])
            await db.people.create_index('status')
            await db.people.create_index('tags')
            await db.site_settings.insert_one({'_id': 'recommendations', 'result_types': ['person']})
            source = await db.people.find_one({'_id': 'person-0001'})
            query = recommendations._candidate_query('person')
            order = [('featured', -1), ('views', -1), ('published_at', -1), ('_id', 1)]
            fallback_before = await db.people.find(query, recommendations.PROJECTION).sort(order).limit(60).to_list(None)
            pool_before = await recommendations._candidate_documents(db, source, 'person', 'person')
            daily_before = [await recommendations.recommendations_for(db, 'person', 'person-0001', rotation_day=day)
                            for day in ('2026-10-21', '2026-10-22')]

            async def ensure(collection, keys, **options):
                await collection.create_index(keys, **options)

            await recommendations.create_recommendation_indexes(ensure, db)
            fallback_after = await db.people.find(query, recommendations.PROJECTION).sort(order).limit(60).to_list(None)
            assert fallback_after == fallback_before
            assert await recommendations._candidate_documents(db, source, 'person', 'person') == pool_before
            for day, expected in zip(('2026-10-21', '2026-10-22'), daily_before):
                assert await recommendations.recommendations_for(db, 'person', 'person-0001', rotation_day=day) == expected
            explained = await db.command({'explain': {'find': 'people', 'filter': query,
                                                    'sort': dict(order), 'limit': 60},
                                          'verbosity': 'executionStats'})
            assert explained['executionStats']['nReturned'] == 60
            assert explained['executionStats']['totalDocsExamined'] <= 80
        finally:
            assert db.name == name and name.startswith('humorpedia_perf_test_')
            await client.drop_database(name)
            client.close()

    asyncio.run(check())
