const DEFAULT_SERVER_URL = "https://recruitment.awos.provectus.pro";

/**
 * Returns the AWOS server base URL.
 *
 * Uses `AWOS_SERVER_URL` env var if set, otherwise the production default.
 */
export function resolveServerUrl(): string {
  return process.env.AWOS_SERVER_URL || DEFAULT_SERVER_URL;
}
