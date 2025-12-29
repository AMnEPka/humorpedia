FROM node:20-slim

WORKDIR /app

COPY package.json /app/
RUN yarn install

COPY . /app

# Create empty public/media directory to prevent webpack from scanning 3000+ images
# Media files are served by backend, so frontend doesn't need them in its filesystem
RUN mkdir -p /app/public/media && touch /app/public/media/.gitkeep

EXPOSE 3000

CMD ["yarn", "start"]
