import locations from './locations.json';

export { locations };

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
