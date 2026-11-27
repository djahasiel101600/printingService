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
  // One-line form for the map search.
  fullAddress: "Dela Pena's Store, Purok 1, Santa Ana, Tubay, Agusan del Norte",
};
const SHOP_MAP_URL = `https://www.google.com/maps/@9.1943064,125.5627068,37a,75y,185.96h,65.01t/data=!3m7!1e1!3m5!1sb311B1FXQSsrlAxj3s8AVQ!2e0!6shttps:%2F%2Fstreetviewpixels-pa.clients6.google.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D24.989055609572674%26panoid%3Db311B1FXQSsrlAxj3s8AVQ%26yaw%3D185.9583605236215!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI2MTEyMy4wIKXMDSoASAFQAw%3D%3D`;

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
          English, and pay online. We print it and let you know when it's ready.
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

        <div className="mt-6 grid gap-6 rounded-2xl border bg-card p-6 shadow-sm sm:grid-cols-[1fr_auto] sm:items-center sm:p-8">
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

          <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
            <a href={SHOP_MAP_URL} target="_blank" rel="noopener noreferrer">
              <ExternalLink aria-hidden className="mr-2 h-4 w-4" />
              Open in Maps
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </Button>
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