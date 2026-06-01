<script>
  export let location;
</script>

<article class="location-card">
  <a href={`/maps/${location.slug}/`}>
    <img src={location.image} alt={`Generated satellite-style view of ${location.title}`} loading="lazy" />
    <div>
      <h3>{location.title}</h3>
      <p>{location.summary}</p>
      <p class="fineprint">{location.region} / {location.category}</p>
    </div>
  </a>
</article>
