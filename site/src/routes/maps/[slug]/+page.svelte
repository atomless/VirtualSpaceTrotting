<script>
  import LocationList from '$lib/components/LocationList.svelte';
  import SiteSidebar from '$lib/components/SiteSidebar.svelte';

  export let data;
  const { location } = data;
</script>

<div class="layout">
  <article>
    <header>
      <h1>{location.title}</h1>
      <p>{location.summary}</p>
      <ul class="meta-list">
        <li>{location.category}</li>
        <li>{location.region}</li>
        <li>{location.syntheticCoordinates}</li>
        <li>{location.views.toLocaleString()} views</li>
      </ul>
    </header>

    <figure class="detail-image">
      <img src={location.image} alt={`Generated satellite-style view of ${location.title}`} />
      <figcaption>Fictional generated imagery. Not a real map tile or real place.</figcaption>
    </figure>

    <section class="panel" aria-labelledby="about-location">
      <h2 id="about-location">About This Map</h2>
      <p>{location.description}</p>
      <ul class="inline-list">
        {#each location.tags as tag}
          <li>{tag}</li>
        {/each}
      </ul>
    </section>

    <section aria-labelledby="related-maps">
      <h2 id="related-maps">More Imaginary Maps</h2>
      <LocationList locations={data.related} />
    </section>
  </article>

  <SiteSidebar />
</div>
