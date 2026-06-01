<script>
  import LocationList from '$lib/components/LocationList.svelte';
  import SiteSidebar from '$lib/components/SiteSidebar.svelte';

  export let data;
</script>

<div class="layout">
  <section aria-labelledby="category-title">
    <h1 id="category-title">{data.category.title}</h1>
    <p>{data.category.count} fictional generated maps in this category.</p>
    <LocationList locations={data.locations} />
  </section>

  <SiteSidebar />
</div>
