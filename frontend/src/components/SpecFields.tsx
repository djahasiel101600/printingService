import { ChevronDown, ChevronUp, Contrast, Palette } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  orientationLabel,
  paperSizeLabel,
  paperSourceLabel,
  paperTypeLabel,
  qualityLabel,
  sidesLabel,
} from "@/lib/constants";
import type { Capabilities, PrintSpecification } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SpecFieldsProps {
  capabilities: Capabilities | null;
  value: PrintSpecification;
  onChange: (spec: PrintSpecification) => void;
  /** Show the Portrait/Landscape control — it only affects picture files. */
  showOrientation?: boolean;
  /**
   * "basic"    → the choices that change the price: color, paper type, special instructions.
   * "advanced" → everything else (size, sides, quality, copies, orientation, borderless, …).
   * "all"      → the original single list, so existing callers keep working unchanged.
   */
  section?: "basic" | "advanced" | "all";
}

export const DEFAULT_SPEC: PrintSpecification = {
  media_size: "ps_a4",
  media_type: "pt_plainpaper",
  color_mode: "mono",
  sides: "none",
  print_quality: "normal",
  copies: 1,
  borderless: false,
  orientation: "portrait",
  source: "auto",
  reverse_order: false,
  collate: true,
  free_text_instructions: "",
};

/** The fields that live under "Advanced settings", so the page can reset just those. */
export const ADVANCED_SPEC_KEYS = [
  "media_size",
  "sides",
  "print_quality",
  "copies",
  "borderless",
  "orientation",
  "source",
  "reverse_order",
  "collate",
] as const satisfies readonly (keyof PrintSpecification)[];

/** One-line, plain-language hint per paper type. Unknown types simply show no hint. */
function paperTypeHint(type: string): string | undefined {
  const t = type.toLowerCase();
  if (t.includes("plain")) return "Everyday documents";
  if (t.includes("photo") || t.includes("glossy")) return "Sharp, glossy photos";
  if (t.includes("matte")) return "Soft, no-glare finish";
  return undefined;
}

const INSTRUCTION_IDEAS = [
  "Staple the pages together",
  "Print pages 1–5 only",
  "Print the first 5 pages in color",
];

/** A whole-box radio choice: big tap target, clear selected state, optional icon and hint. */
function ChoiceCard({
  id,
  value,
  selected,
  disabled,
  title,
  hint,
  icon,
}: {
  id: string;
  value: string;
  selected: boolean;
  disabled?: boolean;
  title: string;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <Label
      htmlFor={id}
      className={cn(
        "flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
        selected ? "border-primary bg-primary/5" : "hover:bg-accent/50",
        disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
      )}
    >
      <RadioGroupItem value={value} id={id} disabled={disabled} className="mt-0.5" />
      <span className="min-w-0 space-y-0.5">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          {icon}
          {title}
        </span>
        {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
      </span>
    </Label>
  );
}

export default function SpecFields({
  capabilities, value, onChange, showOrientation = true, section = "all",
}: SpecFieldsProps) {
  const [advanced, setAdvanced] = useState(false);

  function update<K extends keyof PrintSpecification>(key: K, val: PrintSpecification[K]) {
    onChange({ ...value, [key]: val });
  }

  const sizes = capabilities?.paperSizes ?? [];
  const currentSize = sizes.find((s) => s.paperSize === value.media_size) ?? sizes[0];
  const typesForSize = currentSize?.paperTypes ?? [];
  const currentType = typesForSize.find((t) => t.paperType === value.media_type) ?? typesForSize[0];

  const qualities = currentType?.printQualities ?? ["draft", "normal", "high"];
  const sources = currentType?.paperSources ?? ["auto"];
  const supportsDuplex = currentType?.doubleSided ?? true;

  // ------------------------------------------------------------------ basic
  const colorField = (
    <div className="space-y-1.5">
      <Label id="color-label">Color</Label>
      <RadioGroup
        aria-labelledby="color-label"
        value={value.color_mode}
        onValueChange={(v) => update("color_mode", v as "color" | "mono")}
        className="grid grid-cols-1 gap-2 sm:grid-cols-2"
      >
        <ChoiceCard
          id="cm-mono"
          value="mono"
          selected={value.color_mode === "mono"}
          title="Black & white"
          hint="Text, forms and everyday documents"
          icon={<Contrast className="h-4 w-4" aria-hidden="true" />}
        />
        <ChoiceCard
          id="cm-color"
          value="color"
          selected={value.color_mode === "color"}
          title="Color"
          hint="Photos, charts and presentations"
          icon={<Palette className="h-4 w-4" aria-hidden="true" />}
        />
      </RadioGroup>
    </div>
  );

  const paperTypeField = (
    <div className="space-y-1.5">
      <Label id="paper-type-label">Paper type</Label>
      <RadioGroup
        aria-labelledby="paper-type-label"
        value={value.media_type}
        onValueChange={(v) => update("media_type", v)}
        className="grid grid-cols-1 gap-2 sm:grid-cols-2"
      >
        {(typesForSize.length > 0 ? typesForSize : [{ paperType: "pt_plainpaper" }]).map((t) => (
          <ChoiceCard
            key={t.paperType}
            id={`pt-${t.paperType}`}
            value={t.paperType}
            selected={value.media_type === t.paperType}
            title={paperTypeLabel(t.paperType)}
            hint={paperTypeHint(t.paperType)}
          />
        ))}
      </RadioGroup>
    </div>
  );

  const instructionsField = (
    <div className="space-y-1.5">
      <Label htmlFor="instructions">Special instructions (optional)</Label>
      <Textarea
        id="instructions"
        placeholder="e.g. 'print the first 5 pages in color, rest in black & white'"
        value={value.free_text_instructions ?? ""}
        onChange={(e) => update("free_text_instructions", e.target.value)}
        rows={3}
      />
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted-foreground">Need something specific? Tap to add:</span>
        {INSTRUCTION_IDEAS.map((idea) => (
          <Button
            key={idea}
            type="button"
            variant="outline"
            size="sm"
            className="h-7 rounded-full px-2.5 text-xs font-normal"
            onClick={() => {
              const current = (value.free_text_instructions ?? "").trim();
              if (current.includes(idea)) return;
              update("free_text_instructions", current ? `${current}\n${idea}` : idea);
            }}
          >
            {idea}
          </Button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        A person reads this before printing, so plain words are fine.
      </p>
    </div>
  );

  // --------------------------------------------------------------- advanced
  const sizeField = (
    <div className="space-y-1.5">
      <Label>Paper size</Label>
      <Select value={value.media_size} onValueChange={(v) => update("media_size", v)}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          {sizes.length > 0
            ? sizes.map((s) => (
                <SelectItem key={s.paperSize} value={s.paperSize}>
                  {paperSizeLabel(s.paperSize)}
                </SelectItem>
              ))
            : <SelectItem value="ps_a4">{paperSizeLabel("ps_a4")}</SelectItem>}
        </SelectContent>
      </Select>
    </div>
  );

  const sidesField = (
    <div className="space-y-1.5">
      <Label>Sides</Label>
      <RadioGroup
        value={value.sides}
        onValueChange={(v) => update("sides", v as "none" | "long" | "short")}
        className="grid grid-cols-1 gap-2 sm:grid-cols-3"
      >
        <div className="flex items-center space-x-2 rounded-md border p-2.5">
          <RadioGroupItem value="none" id="s-none" />
          <Label htmlFor="s-none" className="cursor-pointer font-normal">{sidesLabel("none")}</Label>
        </div>
        <div className="flex items-center space-x-2 rounded-md border p-2.5">
          <RadioGroupItem value="long" id="s-long" disabled={!supportsDuplex} />
          <Label htmlFor="s-long" className="cursor-pointer font-normal">{sidesLabel("long")}</Label>
        </div>
        <div className="flex items-center space-x-2 rounded-md border p-2.5">
          <RadioGroupItem value="short" id="s-short" disabled={!supportsDuplex} />
          <Label htmlFor="s-short" className="cursor-pointer font-normal">{sidesLabel("short")}</Label>
        </div>
      </RadioGroup>
    </div>
  );

  const qualityField = (
    <div className="space-y-1.5">
      <Label>Print quality</Label>
      <Select value={value.print_quality} onValueChange={(v) => update("print_quality", v as "draft" | "normal" | "high")}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          {qualities.map((q) => (
            <SelectItem key={q} value={q}>{qualityLabel(q)}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const copiesField = (
    <div className="space-y-1.5">
      <Label htmlFor="copies">Copies</Label>
      <Input
        id="copies"
        type="number"
        min={1}
        max={99}
        value={value.copies}
        onChange={(e) => update("copies", Math.min(99, Math.max(1, parseInt(e.target.value) || 1)))}
      />
    </div>
  );

  const orientationField = showOrientation ? (
    <div className="space-y-1.5">
      <Label>Orientation (pictures)</Label>
      <RadioGroup
        value={value.orientation}
        onValueChange={(v) => update("orientation", v as "portrait" | "landscape")}
        className="grid grid-cols-2 gap-2"
      >
        {(["portrait", "landscape"] as const).map((option) => (
          <div key={option} className="flex items-center space-x-2 rounded-md border p-2.5">
            <RadioGroupItem value={option} id={`orientation-${option}`} />
            <Label htmlFor={`orientation-${option}`} className="cursor-pointer font-normal">
              {orientationLabel(option)}
            </Label>
          </div>
        ))}
      </RadioGroup>
      <p className="text-xs text-muted-foreground">
        How the picture sits on the sheet — landscape turns it so it uses the full
        page. PDFs and documents keep their own layout.
      </p>
    </div>
  ) : null;

  const borderlessField = (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div>
        <Label>Borderless printing</Label>
        <p className="text-xs text-muted-foreground">Print to the edge of the page.</p>
      </div>
      <Switch
        checked={value.borderless}
        onCheckedChange={(v) => update("borderless", v)}
        disabled={!currentType?.borderless}
      />
    </div>
  );

  const extraOptions = (
    <>
      <div className="space-y-1.5">
        <Label>Paper source</Label>
        <Select value={value.source} onValueChange={(v) => update("source", v)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {sources.map((s) => (
              <SelectItem key={s} value={s}>{paperSourceLabel(s)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox id="collate" checked={value.collate} onCheckedChange={(v) => update("collate", v === true)} />
        <Label htmlFor="collate" className="font-normal">Collate multi-copy jobs</Label>
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox id="reverse" checked={value.reverse_order} onCheckedChange={(v) => update("reverse_order", v === true)} />
        <Label htmlFor="reverse" className="font-normal">Reverse page order</Label>
      </div>
    </>
  );

  // --------------------------------------------------------------- sections
  if (section === "basic") {
    return (
      <div className="space-y-5">
        {colorField}
        {paperTypeField}
        {instructionsField}
      </div>
    );
  }

  if (section === "advanced") {
    return (
      <div className="space-y-4">
        {sizeField}
        {sidesField}
        {qualityField}
        {copiesField}
        {orientationField}
        {borderlessField}
        <div className="space-y-4 rounded-md border bg-muted/30 p-3">
          <p className="text-sm font-medium">More options</p>
          {extraOptions}
        </div>
      </div>
    );
  }

  // "all": the original layout and order, with the nested toggle kept.
  return (
    <div className="space-y-4">
      {sizeField}
      {paperTypeField}
      {colorField}
      {sidesField}
      {qualityField}
      {copiesField}
      {orientationField}
      {borderlessField}
      {instructionsField}

      <div className="rounded-md border">
        <Button
          type="button"
          variant="ghost"
          className="w-full justify-between px-3"
          onClick={() => setAdvanced(!advanced)}
        >
          <span className="text-sm font-medium">Advanced options</span>
          {advanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>
        {advanced && <div className="space-y-4 border-t p-3">{extraOptions}</div>}
      </div>
    </div>
  );
}