FROM node:20-slim

WORKDIR /app

# Copy package files
COPY website/package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application
COPY website .

# Build the application
RUN npm run build

# Expose the port
EXPOSE 3000

# Start the application
CMD ["npm", "run", "dev"]
