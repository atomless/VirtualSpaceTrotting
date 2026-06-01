<script>
  import LocationList from '$lib/components/LocationList.svelte';
  import SiteSidebar from '$lib/components/SiteSidebar.svelte';

  export let data;
</script>

<div class="layout">
  <div>
    <section class="hero panel" aria-labelledby="featured-map">
      <figure>
        <img src={data.featured.image} alt={`Generated satellite-style view of ${data.featured.title}`} />
      </figure>
      <div>
        <h2 id="featured-map">Today's Most Popular Imaginary Map</h2>
        <p>
          <a href={`/maps/${data.featured.slug}/`}>{data.featured.title}</a>
          is a fictional generated location from {data.featured.region}.
        </p>
        <ul class="meta-list">
          <li>{data.featured.category}</li>
          <li>{data.featured.syntheticCoordinates}</li>
          <li>{data.featured.views.toLocaleString()} views</li>
        </ul>
        <p class="fineprint">No real-world satellite tiles, addresses, or locations are used.</p>
      </div>
    </section>

    <section aria-labelledby="latest-maps">
      <h2 id="latest-maps">Latest Maps</h2>
      <LocationList locations={data.latest} />
    </section>

    <section class="panel" aria-labelledby="popular-categories">
      <h2 id="popular-categories">Popular Categories</h2>
      <ul class="inline-list">
        {#each data.categories as category}
          <li>
            <a href={`/categories/${category.slug}/`}>{category.title}</a>
            <span class="fineprint">{category.count} maps</span>
          </li>
        {/each}
      </ul>
    </section>
  </div>

  <SiteSidebar />
</div>
