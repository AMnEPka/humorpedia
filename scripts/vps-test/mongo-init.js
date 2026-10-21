const appDb = db.getSiblingDB('humorpedia');
appDb.createUser({
  user: 'humorpedia_app',
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: 'readWrite', db: 'humorpedia' }]
});
