import { latestLocations } from '$lib/data/locations.js';

export const prerender = true;

export function load() {
  return {
    locations: latestLocations
  };
}
