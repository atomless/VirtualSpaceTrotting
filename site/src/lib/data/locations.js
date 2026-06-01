import locations from './locations.json';

export { locations };
export const PAGE_SIZE = 12;

export function slugify(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

export const categories = Array.from(
  locations.reduce((map, location) => {
    const slug = slugify(location.category);
    const current = map.get(slug) ?? {
      slug,
      title: location.category,
      count: 0,
      views: 0
    };
    current.count += 1;
    current.views += location.views;
    map.set(slug, current);
    return map;
  }, new Map()).values()
).sort((a, b) => a.title.localeCompare(b.title));

export const latestLocations = [...locations].sort((a, b) => b.dateAdded.localeCompare(a.dateAdded));
export const popularLocations = [...locations].sort((a, b) => b.views - a.views);

export function totalPagesFor(items, pageSize = PAGE_SIZE) {
  return Math.max(1, Math.ceil(items.length / pageSize));
}

export function paginateItems(items, page, pageSize = PAGE_SIZE) {
  const currentPage = Number(page);
  const totalPages = totalPagesFor(items, pageSize);
  if (!Number.isInteger(currentPage) || currentPage < 1 || currentPage > totalPages) {
    return null;
  }
  const start = (currentPage - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    currentPage,
    totalPages,
    pageSize,
    totalItems: items.length
  };
}

export function getLocationsPage(page) {
  return paginateItems(latestLocations, page);
}

export function getLocation(slug) {
  return locations.find((location) => location.slug === slug);
}

export function getCategory(slug) {
  return categories.find((category) => category.slug === slug);
}

export function getLocationsByCategory(slug) {
  const category = getCategory(slug);
  if (!category) return [];
  return locations.filter((location) => slugify(location.category) === slug);
}

export function getLocationsByCategoryPage(slug, page) {
  return paginateItems(getLocationsByCategory(slug), page);
}
