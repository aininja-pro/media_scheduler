/**
 * Application Configuration
 *
 * Centralizes environment-specific settings.
 * Vite exposes environment variables prefixed with VITE_ to the client.
 */

// API Base URL - defaults to localhost if not set
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8081';

// Check if running in development mode
export const IS_DEV = import.meta.env.DEV;

// Check if running in production mode
export const IS_PROD = import.meta.env.PROD;

// Log configuration in development
if (IS_DEV) {
  console.log('🔧 App Configuration:', {
    API_BASE_URL,
    IS_DEV,
    IS_PROD
  });
}
