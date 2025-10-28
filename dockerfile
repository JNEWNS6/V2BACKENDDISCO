FROM node:20-alpine
WORKDIR /app

# deps
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev

# source
COPY . .

EXPOSE 3000
CMD ["node","server.js"]
