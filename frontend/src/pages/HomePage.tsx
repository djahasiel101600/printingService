import {
  CheckCircle2,
  FileText,
  Printer,
  QrCode,
  ShieldCheck,
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
    desc: "Your job goes to our Epson printer, and you can follow its progress until it's ready for pickup.",
  },
];

const ASSURANCES = [
  "No printer knowledge needed",
  "Every job reviewed by a person",
  "Track your order anytime",
];

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
