import { popularLocations } from '$lib/data/locations.js';

export const prerender = true;

export function load() {
  return {
    locations: popularLocations.slice(0, 4)
  };
}
