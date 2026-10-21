"""Восстановление проекций сезонов на standalone Mongo; по умолчанию только просмотр."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parser():
    result=argparse.ArgumentParser(description=__doc__)
    result.add_argument('--db-name',required=True)
    result.add_argument('--season-id')
    result.add_argument('--apply',action='store_true')
    result.add_argument('--recover-claim',action='store_true')
    result.add_argument('--expected-token')
    result.add_argument('--confirm-worker-stopped',action='store_true')
    result.add_argument('--actor',default='')
    result.add_argument('--reason',default='')
    return result


async def run(args):
    from utils.database import get_db,close_db
    from services.season_projection import rebuild_season_projection,retry_season_projection,recover_season_claim
    previous=os.environ.get('DB_NAME')
    os.environ['DB_NAME']=args.db_name
    try:
        db=await get_db()
        if db.name!=args.db_name:
            raise ValueError('Подключённая БД не совпадает с --db-name')
        query={'_id':args.season_id} if args.season_id else {'page_collection':'kvn'}
        result=[]
        async for season in db.seasons.find(query).sort('_id',1):
            claim=season.get('_write_claim') or {}
            status=(season.get('_projection') or {}).get('state','ready')
            entry={'season_id':season['_id'],'updated_at':season.get('updated_at'),
                   'projection_status':status,'claim_token':claim.get('token'),'applied':False}
            if args.apply:
                if args.recover_claim:
                    entry.update(await recover_season_claim(db,season['_id'],args.expected_token,
                        worker_stopped=args.confirm_worker_stopped,actor=args.actor,reason=args.reason))
                else:
                    saved=await (retry_season_projection(db,season['_id'],season.get('updated_at')) if status!='ready'
                                 else rebuild_season_projection(db,season))
                    entry['projection_status']=saved['projection_status']
                entry['applied']=True
            result.append(entry)
        if args.season_id and not result:
            raise ValueError('Сезон не найден')
        return {'database':db.name,'items':result,'total':len(result)}
    finally:
        await close_db()
        if previous is None: os.environ.pop('DB_NAME',None)
        else: os.environ['DB_NAME']=previous


def main(argv=None):
    command=parser();args=command.parse_args(argv)
    if not (os.environ.get('MONGO_URL') or os.environ.get('MONGO_HOST')):
        command.error('Задайте MONGO_URL или MONGO_HOST явно')
    if args.recover_claim and args.apply and not (args.season_id and args.expected_token and args.confirm_worker_stopped and args.actor.strip() and args.reason.strip()):
        command.error('--recover-claim --apply требует --season-id, --expected-token, --confirm-worker-stopped, --actor и --reason')
    try:
        result=asyncio.run(run(args))
    except Exception as exc:
        detail=getattr(exc,'detail',str(exc))
        print(json.dumps({'error':detail},ensure_ascii=False),file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 0 if not any(item['projection_status']=='error' and item['applied'] and not args.recover_claim for item in result['items']) else 1


if __name__=='__main__': raise SystemExit(main())
