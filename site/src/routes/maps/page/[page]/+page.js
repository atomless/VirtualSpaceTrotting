import { error } from '@sveltejs/kit';
import { getLocationsPage, totalPagesFor, latestLocations } from '$lib/data/locations.js';

export const prerender = true;

export function entries() {
  return Array.from({ length: totalPagesFor(latestLocations) - 1 }, (_, index) => ({
    page: String(index + 2)
  }));
}

export function load({ params }) {
  const page = getLocationsPage(Number(params.page));
  if (!page || page.currentPage === 1) error(404, 'Map page not found');
  return {
    title: `Browse Maps: Page ${page.currentPage}`,
    locations: page.items,
    page
  };
}
