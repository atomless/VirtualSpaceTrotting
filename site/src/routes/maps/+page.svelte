<script>
  import LocationList from '$lib/components/LocationList.svelte';
  import SiteSidebar from '$lib/components/SiteSidebar.svelte';

  export let data;
</script>

<div class="layout">
  <section aria-labelledby="all-maps">
    <h1 id="all-maps">Browse Maps</h1>
    <p>Satellite-style views of places that do not exist.</p>
    <LocationList locations={data.locations} />
  </section>

  <SiteSidebar />
</div>
