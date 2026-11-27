import {
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

export default function HomePage() {
  return (
    <div className="space-y-16 sm:space-y-20">
      {/* ------------------------------------------------------------ hero */}
      <section
        aria-labelledby="hero-title"
        className="rounded-2xl border bg-muted/40 px-6 py-10 sm:px-10 sm:py-14"
      >
        <h1
          id="hero-title"
          className="max-w-2xl text-balance text-3xl font-bold tracking-tight sm:text-5xl"
        >
          Print anything. No printer knowledge required.
        </h1>
        <p className="mt-4 max-w-xl text-base text-muted-foreground sm:text-lg">
          Upload your documents or photos, tell us what you need in plain
          language, and pay online. We print it and let you know when it's ready.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg" className="w-full sm:w-auto">
            <Link to="/order">Start a print order</Link>
          </Button>
          <Button
            asChild
            variant="outline"
            size="lg"
            className="w-full sm:w-auto"
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
        <p className="mt-6 flex items-start gap-2 border-t pt-5 text-sm text-muted-foreground sm:items-center">
          <MapPin
            aria-hidden
            className="mt-0.5 h-4 w-4 shrink-0 text-primary sm:mt-0"
          />
          <span>
            Printed at {SHOP.name} in Santa Ana, Tubay, Agusan del Norte.
          </span>
        </p>
      </section>

      {/* ---------------------------------------------------- walkthrough */}
      <section aria-labelledby="walkthrough-title">
        <h2 id="walkthrough-title" className="text-2xl font-semibold tracking-tight">
          See it in action
        </h2>
        <p className="mt-1 text-muted-foreground">
          A short walkthrough — upload your file, we review it, you pay, then
          collect your prints.
        </p>

        <div className="mt-6 overflow-hidden rounded-2xl border bg-muted shadow-sm">
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
      </section>

      {/* ------------------------------------------------------ how it works */}
      <section aria-labelledby="how-title">
        <h2 id="how-title" className="text-2xl font-semibold tracking-tight">
          How it works
        </h2>
        <p className="mt-1 text-muted-foreground">
          Four steps from file to finished print.
        </p>

        <ol className="mt-10 grid gap-10 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              // On large screens a thin line links each step's icon to the next.
              className="relative space-y-3 lg:after:absolute lg:after:left-16 lg:after:right-[-0.75rem] lg:after:top-6 lg:after:h-px lg:after:bg-border lg:last:after:hidden"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary ring-4 ring-background">
                <step.icon aria-hidden className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">
                  Step {i + 1}
                </p>
                <h3 className="font-semibold">{step.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {step.desc}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* ------------------------------------------------------- visit the shop */}
      <section aria-labelledby="visit-title">
        <h2 id="visit-title" className="text-2xl font-semibold tracking-tight">
          Visit the shop
        </h2>
        <p className="mt-1 text-muted-foreground">
          Your prints are made, and picked up, here.
        </p>

        <div className="mt-6 overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div className="grid md:grid-cols-2 p-2">
            {/* The real storefront, so people know exactly what to look for. */}
            <figure className="relative bg-muted md:order-last">
              <img
                src={SHOP_PHOTO.src}
                alt={SHOP_PHOTO.alt}
                width={SHOP_PHOTO.width}
                height={SHOP_PHOTO.height}
                loading="lazy"
                decoding="async"
                className="aspect-[4/3] h-full w-full object-cover object-[65%_center] md:aspect-auto md:min-h-[18rem] rounded-t-lg"
              />
              <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-4 pb-3 pt-8 text-xs text-white sm:text-sm">
                Look for the blue signboard that reads &ldquo;Dela Peña Sari
                Sari Store&rdquo;.
              </figcaption>
            </figure>

            <div className="flex flex-col justify-between gap-6 p-6 sm:p-8">
              <dl className="space-y-5">
                <div className="flex items-start gap-3">
                  <Store
                    aria-hidden
                    className="mt-0.5 h-5 w-5 shrink-0 text-primary"
                  />
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">
                      Printing shop
                    </dt>
                    <dd className="font-semibold">{SHOP.name}</dd>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <UserRound
                    aria-hidden
                    className="mt-0.5 h-5 w-5 shrink-0 text-primary"
                  />
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">
                      Owner
                    </dt>
                    <dd className="font-semibold">{SHOP.owner}</dd>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <MapPin
                    aria-hidden
                    className="mt-0.5 h-5 w-5 shrink-0 text-primary"
                  />
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

              <Button asChild variant="outline" size="lg" className="w-full sm:w-auto sm:self-start">
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
        className="flex flex-col items-start justify-between gap-4 border-t pt-10 sm:flex-row sm:items-center"
      >
        <div>
          <h2 id="cta-title" className="text-xl font-semibold tracking-tight">
            Ready to print?
          </h2>
          <p className="text-sm text-muted-foreground">
            Upload your first file and we'll take it from there.
          </p>
        </div>
        <Button asChild size="lg" className="w-full sm:w-auto">
          <Link to="/order">Start a print order</Link>
        </Button>
      </section>
    </div>
  );
}