import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  ExternalLink,
  FileText,
  MapPin,
  Printer,
  QrCode,
  ShieldCheck,
  Store,
  UserRound,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { fetchAllCatalogueProducts } from "@/lib/catalogue";
import { formatPeso } from "@/lib/utils";

const STEPS = [
  {
    icon: FileText,
    title: "Upload your files",
    desc: "Add PDFs or images, then describe how you want them printed in plain language.",
  },
  {
    icon: QrCode,
    title: "Pay with QR Ph",
    desc: "Pay in full or make a partial down payment. Payments are processed securely by PayMongo.",
  },
  {
    icon: ShieldCheck,
    title: "We review your job",
    desc: "A real person checks your files and instructions before anything is printed.",
  },
  {
    icon: Printer,
    title: "Printed and ready",
    desc: "Your job goes to our Epson printer, and you can follow its progress until it's ready for pickup at our shop.",
  },
];

const ASSURANCES = [
  "No printer knowledge needed",
  "Every job reviewed by a person",
  "Track your order anytime",
];

// Shop details live in one place so the hero, the visit section and any
// future footer or contact page can't drift apart.
const SHOP = {
  name: "Dela Pena's Store",
  owner: "Melanie Dela Pena",
  addressLines: ["Purok 1, Santa Ana", "Tubay, Agusan del Norte"],
  // Pin location, taken from the Google Maps link below.
  lat: 9.194298,
  lng: 125.562711,
};
// "Open in Maps" button: your hand-picked link.
const SHOP_MAP_URL = `https://www.google.com/maps/place//@9.1942776,125.5627642,67m/data=!3m1!1e3!4m6!1m5!3m4!2zOcKwMTEnMzkuNSJOIDEyNcKwMzMnNDUuOCJF!8m2!3d9.194298!4d125.562711?entry=ttu&g_ep=EgoyMDI2MTEyMy4wIKXMDSoASAFQAw%3D%3D`;
// Storefront photo. Put the file in your project's public/images/ folder
// (it is included next to this file) so this path resolves.
const SHOP_PHOTO = {
  src: "/images/dela-pena-store.jpg",
  width: 1342,
  height: 700,
  alt: "Front of the shop: a blue signboard reading Dela Peña Sari Sari Store above a covered entrance with bags and goods on display",
};
// Map shown on the page itself (no API key needed). Change z to zoom in/out.
const SHOP_MAP_EMBED_URL = `https://maps.google.com/maps?q=${SHOP.lat},${SHOP.lng}&z=17&output=embed`;

// Product walkthrough clip (hosted by demosmith). Swap this one constant if the
// video is re-recorded — nothing else on the page depends on it.
const WALKTHROUGH_EMBED_URL = "https://public.demosmith.ai/b9e7b3a3/embed.html";

// Purely illustrative content for the order slip shown in the hero.
const SAMPLE_SLIP = {
  file: "school-project.pdf",
  detail: "24 pages · Black & white · 2 copies",
  progress: [
    "Files uploaded",
    "Paid with QR Ph",
    "Reviewed by our team",
    "Ready for pickup",
  ],
};

/** Decorative "order slip" that shows, at a glance, what ordering looks like. */
function OrderSlip() {
  return (
    <div aria-hidden className="relative mx-auto w-full max-w-sm lg:mx-0 lg:ml-auto">
      {/* Paper stack behind the slip */}
      <div className="absolute inset-0 -rotate-6 rounded-2xl border bg-card/70 shadow-sm" />
      <div className="absolute inset-0 rotate-3 rounded-2xl border bg-card/80 shadow-sm" />

      <div className="relative rounded-2xl border bg-card shadow-xl lg:-rotate-1">
        <div className="flex items-start gap-3 p-5">
          <div className="rounded-lg bg-primary/10 p-2.5 text-primary">
            <FileText className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Sample order</p>
            <p className="truncate font-semibold">{SAMPLE_SLIP.file}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {SAMPLE_SLIP.detail}
            </p>
          </div>
        </div>

        {/* Perforated tear line */}
        <div className="relative border-t border-dashed">
          <span className="absolute -left-3 -top-3 h-6 w-6 rounded-full border bg-background" />
          <span className="absolute -right-3 -top-3 h-6 w-6 rounded-full border bg-background" />
        </div>

        <ul className="space-y-3 p-5 pt-6">
          {SAMPLE_SLIP.progress.map((label, i) => {
            const isLast = i === SAMPLE_SLIP.progress.length - 1;
            return (
              <li key={label} className="flex items-center gap-3 text-sm">
                <span
                  className={
                    isLast
                      ? "flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground"
                      : "flex h-6 w-6 items-center justify-center rounded-full bg-primary/15 text-primary"
                  }
                >
                  <Check className="h-3.5 w-3.5" />
                </span>
                <span className={isLast ? "font-semibold" : "text-muted-foreground"}>
                  {label}
                </span>
                {isLast && (
                  <span className="ml-auto h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse" />
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

export default function HomePage() {
  const featuredProductsQuery = useQuery({
    queryKey: ["catalogue-products", "featured"],
    queryFn: () => fetchAllCatalogueProducts({ featured: true }),
    retry: false,
  });
  const featuredProducts = featuredProductsQuery.data ?? [];

  return (
    <div className="space-y-20 sm:space-y-28">
      {/* ------------------------------------------------------------ hero */}
      <section
        aria-labelledby="hero-title"
        className="relative overflow-hidden rounded-3xl border bg-muted/40 px-6 py-12 sm:px-12 sm:py-16"
      >
        {/* Soft dotted "paper" texture */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 text-primary/15 [background-image:radial-gradient(currentColor_1px,transparent_1px)] [background-size:20px_20px] [mask-image:linear-gradient(to_bottom_left,black,transparent_70%)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl"
        />

        <div className="relative grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <h1
              id="hero-title"
              className="max-w-2xl text-balance text-4xl font-bold tracking-tight sm:text-6xl sm:leading-[1.05]"
            >
              Print anything. No printer knowledge required.
            </h1>
            <p className="mt-5 max-w-xl text-base text-muted-foreground sm:text-lg">
              Upload your documents or photos, tell us what you need in plain
              language, and pay online. We print it and let you know when it's
              ready.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="w-full sm:w-auto">
                <Link to="/order">
                  Start a print order
                  <ArrowRight aria-hidden className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                size="lg"
                className="w-full bg-background/60 sm:w-auto"
              >
                <Link to="/track">Track an order</Link>
              </Button>
            </div>

            <ul className="mt-8 flex flex-col gap-2 text-sm text-muted-foreground sm:flex-row sm:flex-wrap sm:gap-x-6">
              {ASSURANCES.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <CheckCircle2
                    aria-hidden
                    className="h-4 w-4 shrink-0 text-primary"
                  />
                  {item}
                </li>
              ))}
            </ul>

            {/* Who is behind it, and where, right where first-time visitors look. */}
            <p className="mt-8 flex items-start gap-2 border-t pt-5 text-sm text-muted-foreground sm:items-center">
              <MapPin
                aria-hidden
                className="mt-0.5 h-4 w-4 shrink-0 text-primary sm:mt-0"
              />
              <span>
                Printed at {SHOP.name} in Santa Ana, Tubay, Agusan del Norte.
              </span>
            </p>
          </div>

          <OrderSlip />
        </div>
      </section>

      {/* ------------------------------------- how it works + walkthrough */}
      <section aria-labelledby="how-title">
        <div className="max-w-2xl">
          <h2 id="how-title" className="text-3xl font-bold tracking-tight sm:text-4xl">
            How it works
          </h2>
          <p className="mt-2 text-muted-foreground">
            Four steps from file to finished print.
          </p>
        </div>

        <div className="mt-10 grid gap-10 lg:grid-cols-2 lg:gap-14">
          <ol>
            {STEPS.map((step, i) => (
              <li
                key={step.title}
                // A thin line connects each step's icon to the next.
                className="relative pb-10 pl-16 last:pb-0 before:absolute before:bottom-0 before:left-6 before:top-14 before:w-px before:bg-border last:before:hidden"
              >
                <div className="absolute left-0 top-0 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm ring-4 ring-background">
                  <step.icon aria-hidden className="h-5 w-5" />
                </div>
                <p className="text-xs font-medium text-muted-foreground">
                  Step {i + 1}
                </p>
                <h3 className="text-lg font-semibold">{step.title}</h3>
                <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                  {step.desc}
                </p>
              </li>
            ))}
          </ol>

          {/* Walkthrough clip sits next to the steps it explains. */}
          <div className="lg:sticky lg:top-24 lg:self-start">
            <h3 id="walkthrough-title" className="text-lg font-semibold">
              See it in action
            </h3>
            <p className="mb-4 mt-1 text-sm text-muted-foreground">
              A short walkthrough — upload your file, we review it, you pay,
              then collect your prints.
            </p>
            <div className="overflow-hidden rounded-2xl border bg-muted shadow-lg ring-1 ring-primary/10">
              <div className="aspect-video w-full">
                <iframe
                  src={WALKTHROUGH_EMBED_URL}
                  title="Walkthrough of the print ordering flow"
                  className="h-full w-full border-0"
                  allow="fullscreen; picture-in-picture"
                  allowFullScreen
                  loading="lazy"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Catalogue services are optional: a failed request simply hides this section. */}
      {!featuredProductsQuery.isError &&
        (featuredProductsQuery.isLoading || featuredProducts.length > 0) && (
          <section aria-labelledby="catalogue-title">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="max-w-2xl">
                <h2
                  id="catalogue-title"
                  className="text-3xl font-bold tracking-tight sm:text-4xl"
                >
                  Featured printing services
                </h2>
                <p className="mt-2 text-muted-foreground">
                  Fixed-price services prepared by our shop. Upload one source
                  file and choose your quantity.
                </p>
              </div>
              <Button asChild variant="outline">
                <Link to="/order?mode=catalogue">View all services</Link>
              </Button>
            </div>

            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {featuredProductsQuery.isLoading
                ? [0, 1, 2].map((n) => (
                    <div
                      key={n}
                      aria-hidden
                      className="h-64 rounded-2xl border bg-muted/50 motion-safe:animate-pulse"
                    />
                  ))
                : featuredProducts.map((product) => (
                    <article
                      key={product.id}
                      className="group flex flex-col rounded-2xl border bg-card p-6 shadow-sm transition-shadow hover:shadow-lg"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
                          <Store aria-hidden className="h-5 w-5" />
                        </div>
                        <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                          {product.category}
                        </span>
                      </div>
                      <h3 className="mt-5 text-lg font-semibold">
                        {product.name}
                      </h3>
                      {product.description && (
                        <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                          {product.description}
                        </p>
                      )}
                      <div className="mt-5 border-t border-dashed pt-4">
                        <p className="text-2xl font-bold">
                          {formatPeso(product.price_peso)}
                          <span className="ml-1 text-sm font-normal text-muted-foreground">
                            per {product.unit_label}
                          </span>
                        </p>
                        <Button asChild className="mt-4 w-full">
                          <Link to="/order?mode=catalogue">
                            Order this service{" "}
                            <ArrowRight aria-hidden className="ml-2 h-4 w-4" />
                          </Link>
                        </Button>
                      </div>
                    </article>
                  ))}
            </div>
          </section>
        )}

      {/* ------------------------------------------------------- visit the shop */}
      <section aria-labelledby="visit-title">
        <div className="max-w-2xl">
          <h2 id="visit-title" className="text-3xl font-bold tracking-tight sm:text-4xl">
            Visit the shop
          </h2>
          <p className="mt-2 text-muted-foreground">
            Your prints are made, and picked up, here.
          </p>
        </div>

        <div className="mt-8 overflow-hidden rounded-3xl border bg-card shadow-sm">
          <div className="grid md:grid-cols-2">
            {/* The real storefront, so people know exactly what to look for. */}
            <figure className="relative bg-muted md:order-last">
              <img
                src={SHOP_PHOTO.src}
                alt={SHOP_PHOTO.alt}
                width={SHOP_PHOTO.width}
                height={SHOP_PHOTO.height}
                loading="lazy"
                decoding="async"
                className="aspect-[4/3] h-full w-full object-cover object-[65%_center] md:aspect-auto md:min-h-[20rem]"
              />
              <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-5 pb-4 pt-10 text-xs text-white sm:text-sm">
                Look for the blue signboard that reads &ldquo;Dela Peña Sari
                Sari Store&rdquo;.
              </figcaption>
            </figure>

            <div className="flex flex-col justify-between gap-8 p-6 sm:p-10">
              <dl className="space-y-6">
                <div className="flex items-start gap-4">
                  <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
                    <Store aria-hidden className="h-5 w-5" />
                  </div>
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">
                      Printing shop
                    </dt>
                    <dd className="font-semibold">{SHOP.name}</dd>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
                    <UserRound aria-hidden className="h-5 w-5" />
                  </div>
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">
                      Owner
                    </dt>
                    <dd className="font-semibold">{SHOP.owner}</dd>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
                    <MapPin aria-hidden className="h-5 w-5" />
                  </div>
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">
                      Address
                    </dt>
                    <dd>
                      <address className="not-italic">
                        {SHOP.addressLines.map((line) => (
                          <span key={line} className="block font-semibold">
                            {line}
                          </span>
                        ))}
                      </address>
                    </dd>
                  </div>
                </div>
              </dl>

              <Button
                asChild
                variant="outline"
                size="lg"
                className="w-full sm:w-auto sm:self-start"
              >
                <a href={SHOP_MAP_URL} target="_blank" rel="noopener noreferrer">
                  <ExternalLink aria-hidden className="mr-2 h-4 w-4" />
                  Open in Maps
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              </Button>
            </div>
          </div>

          {/* Map right on the page: visitors see where the shop is without leaving the site. */}
          <div className="aspect-[4/3] w-full border-t bg-muted sm:aspect-[21/9]">
            <iframe
              src={SHOP_MAP_EMBED_URL}
              title={`Map showing the location of ${SHOP.name}`}
              className="h-full w-full border-0"
              loading="lazy"
              allowFullScreen
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------- closing prompt */}
      <section
        aria-labelledby="cta-title"
        className="relative overflow-hidden rounded-3xl bg-primary px-6 py-12 text-primary-foreground sm:px-12 sm:py-14"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 text-primary-foreground/10 [background-image:radial-gradient(currentColor_1px,transparent_1px)] [background-size:20px_20px]"
        />
        <div className="relative flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <h2 id="cta-title" className="text-2xl font-bold tracking-tight sm:text-3xl">
              Ready to print?
            </h2>
            <p className="mt-1 text-primary-foreground/80">
              Upload your first file and we'll take it from there.
            </p>
          </div>
          <Button asChild size="lg" variant="secondary" className="w-full sm:w-auto">
            <Link to="/order">
              Start a print order
              <ArrowRight aria-hidden className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  );
}