FROM node:18-alpine

# Install git and other dependencies
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Clone the Envio Uniswap v4 indexer
RUN git clone https://github.com/enviodev/uniswap-v4-indexer.git .

# Install pnpm
RUN npm install -g pnpm

# Install dependencies
RUN pnpm install

# Copy configuration if it exists
COPY config.yaml ./config.yaml

# Expose Hasura port
EXPOSE 8080

# Create cache directory
RUN mkdir -p /app/cache

# Start the indexer in dev mode
CMD ["pnpm", "envio", "dev"] 