<script>
  import LocationList from '$lib/components/LocationList.svelte';
  import PageNav from '$lib/components/PageNav.svelte';
  import SiteSidebar from '$lib/components/SiteSidebar.svelte';

  export let data;
</script>

<div class="layout">
  <section aria-labelledby="category-title">
    <h1 id="category-title">{data.category.title}: Page {data.page.currentPage}</h1>
    <p>
      {data.category.count} fictional generated maps in this category. Page {data.page.currentPage} of {data.page.totalPages}.
    </p>
    <LocationList locations={data.locations} />
    <PageNav page={data.page} basePath={`/categories/${data.category.slug}`} />
  </section>

  <SiteSidebar />
</div>
