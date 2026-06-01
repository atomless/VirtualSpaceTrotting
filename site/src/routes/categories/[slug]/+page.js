import { error } from '@sveltejs/kit';
import { categories, getCategory, getLocationsByCategoryPage } from '$lib/data/locations.js';

export const prerender = true;

export function entries() {
  return categories.map((category) => ({ slug: category.slug }));
}

export function load({ params }) {
  const category = getCategory(params.slug);
  if (!category) error(404, 'Imaginary category not found');
  const page = getLocationsByCategoryPage(params.slug, 1);
  return {
    category,
    locations: page.items,
    page
  };
}
