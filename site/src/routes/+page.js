import { categories, latestLocations, popularLocations } from '$lib/data/locations.js';

export const prerender = true;

export function load() {
  return {
    categories,
    featured: popularLocations[0],
    latest: latestLocations.slice(0, 6),
    popular: popularLocations.slice(0, 5)
  };
}
