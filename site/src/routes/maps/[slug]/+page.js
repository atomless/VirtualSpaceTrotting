import { error } from '@sveltejs/kit';
import { getLocation, locations, popularLocations } from '$lib/data/locations.js';

export const prerender = true;

export function entries() {
  return locations.map((location) => ({ slug: location.slug }));
}

export function load({ params }) {
  const location = getLocation(params.slug);
  if (!location) error(404, 'Imaginary location not found');
  return {
    location,
    related: popularLocations.filter((entry) => entry.slug !== location.slug).slice(0, 4)
  };
}
