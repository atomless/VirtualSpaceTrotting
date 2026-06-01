import { getLocationsPage } from '$lib/data/locations.js';

export const prerender = true;

export function load() {
  const page = getLocationsPage(1);
  return {
    title: 'Browse Maps',
    locations: page.items,
    page
  };
}
