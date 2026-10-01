import { FileText, Printer, QrCode, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STEPS = [
  { icon: FileText, title: "Upload your files", desc: "PDFs and images — add print instructions in plain language." },
  { icon: QrCode, title: "Pay via QR Ph", desc: "Full or partial down payment, secured by PayMongo." },
  { icon: ShieldCheck, title: "Human review", desc: "A real person reviews your job before it hits the printer." },
  { icon: Printer, title: "Printed & ready", desc: "Sent to our printer via Epson Connect API v2." },
];

export default function HomePage() {
  return (
    <div className="space-y-12">
      <section className="rounded-2xl bg-gradient-to-br from-primary/10 via-background to-background p-8 shadow-sm">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Print anything. No printer knowledge required.
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Upload your documents or photos, tell us what you need in plain English,
          pay online, and we'll print it on our Epson printer. Every job is reviewed
          by a real person before it prints.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link to="/order">Start a Print Order</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/track">Track an Order</Link>
          </Button>
        </div>
      </section>

      <section>
        <h2 className="mb-6 text-xl font-semibold">How it works</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step) => (
            <Card key={step.title}>
              <CardHeader>
                <step.icon className="h-8 w-8 text-primary" />
                <CardTitle className="text-base">{step.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{step.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
