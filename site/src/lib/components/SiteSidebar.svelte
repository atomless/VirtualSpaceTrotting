<script>
  import { categories, popularLocations } from '$lib/data/locations.js';
</script>

<aside aria-label="Browse imaginary locations">
  <section class="panel">
    <h2>Browse Categories</h2>
    <ul class="sidebar-list">
      {#each categories as category}
        <li>
          <a href={`/categories/${category.slug}/`}>{category.title}</a>
          <span class="fineprint">({category.count})</span>
        </li>
      {/each}
    </ul>
  </section>

  <section class="panel">
    <h2>Most Viewed</h2>
    <ol class="sidebar-list">
      {#each popularLocations.slice(0, 5) as location}
        <li>
          <a href={`/maps/${location.slug}/`}>{location.title}</a>
          <span class="fineprint">{location.views.toLocaleString()} views</span>
        </li>
      {/each}
    </ol>
  </section>
</aside>
