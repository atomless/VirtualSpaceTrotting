<script>
  import LocationList from '$lib/components/LocationList.svelte';
  import PageNav from '$lib/components/PageNav.svelte';
  import SiteSidebar from '$lib/components/SiteSidebar.svelte';

  export let data;
</script>

<div class="layout">
  <section aria-labelledby="all-maps">
    <h1 id="all-maps">{data.title}</h1>
    <p>Satellite-style views of places that do not exist. Page {data.page.currentPage} of {data.page.totalPages}.</p>
    <LocationList locations={data.locations} />
    <PageNav page={data.page} basePath="/maps" />
  </section>

  <SiteSidebar />
</div>
