<script>
  import LocationCard from './LocationCard.svelte';

  export let locations = [];
</script>

<ol class="location-list">
  {#each locations as location (location.slug)}
    <li>
      <LocationCard {location} />
    </li>
  {/each}
</ol>
