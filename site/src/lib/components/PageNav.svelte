<script>
  export let page;
  export let basePath;

  $: pages = Array.from({ length: page.totalPages }, (_, index) => index + 1);
  $: pageUrl = (number) => (number === 1 ? `${basePath}/` : `${basePath}/page/${number}/`);
</script>

{#if page.totalPages > 1}
  <nav class="pagination" aria-label="Pagination">
    <ol>
      {#each pages as number}
        <li>
          {#if number === page.currentPage}
            <strong aria-current="page">{number}</strong>
          {:else}
            <a href={pageUrl(number)}>{number}</a>
          {/if}
        </li>
      {/each}
    </ol>
  </nav>
{/if}
