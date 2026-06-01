<script>
  import '../app.css';
</script>

<header class="site-header">
  <div class="inner">
    <div class="brand-row">
      <h1 class="brand"><a href="/">VirtualSpaceTrotting</a></h1>
      <p class="tagline">Imaginary satellite curiosities</p>
    </div>
    <nav aria-label="Primary navigation">
      <ul class="nav-list">
        <li><a href="/">Home</a></li>
        <li><a href="/maps/">Maps</a></li>
        <li><a href="/categories/transport/">Categories</a></li>
        <li><a href="/blog/">Blog</a></li>
      </ul>
    </nav>
  </div>
</header>

<main class="page">
  <slot />
</main>

<footer class="site-footer">
  <div class="inner">
    <p>Every place here is fictional. Every image is generated for this imaginary atlas.</p>
  </div>
</footer>
