import { error } from '@sveltejs/kit';
import { categories, getCategory, getLocationsByCategory, getLocationsByCategoryPage, totalPagesFor } from '$lib/data/locations.js';

export const prerender = true;

export function entries() {
  return categories.flatMap((category) => {
    const totalPages = totalPagesFor(getLocationsByCategory(category.slug));
    return Array.from({ length: totalPages - 1 }, (_, index) => ({
      slug: category.slug,
      page: String(index + 2)
    }));
  });
}

export function load({ params }) {
  const category = getCategory(params.slug);
  if (!category) error(404, 'Imaginary category not found');
  const page = getLocationsByCategoryPage(params.slug, Number(params.page));
  if (!page || page.currentPage === 1) error(404, 'Category page not found');
  return {
    category,
    locations: page.items,
    page
  };
}
