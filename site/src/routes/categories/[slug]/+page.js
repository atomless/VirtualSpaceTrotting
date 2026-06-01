import { error } from '@sveltejs/kit';
import { categories, getCategory, getLocationsByCategory } from '$lib/data/locations.js';

export const prerender = true;

export function entries() {
  return categories.map((category) => ({ slug: category.slug }));
}

export function load({ params }) {
  const category = getCategory(params.slug);
  if (!category) error(404, 'Imaginary category not found');
  return {
    category,
    locations: getLocationsByCategory(params.slug)
  };
}
