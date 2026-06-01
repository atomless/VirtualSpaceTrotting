<script>
  export let data;
</script>

<article>
  <header>
    <h1>Field Notes From Nowhere</h1>
    <p>A short launch note for the first imaginary atlas batch.</p>
  </header>

  <section class="panel">
    <h2>Launch Set 001</h2>
    <p>
      The first VirtualSpaceTrotting set is tuned for old-web browsing: direct links,
      compact metadata, and overhead curiosities that reward slow inspection.
    </p>
    <p>
      These places are not hidden celebrity homes, military sites, or real discoveries.
      They are fictional generated scenes built to feel like satellite browsing without
      borrowing any real map tiles.
    </p>
  </section>

  <section aria-labelledby="blog-maps">
    <h2 id="blog-maps">Maps Mentioned</h2>
    <ul class="sidebar-list">
      {#each data.locations as location}
        <li><a href={`/maps/${location.slug}/`}>{location.title}</a></li>
      {/each}
    </ul>
  </section>
</article>
