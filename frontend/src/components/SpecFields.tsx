import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

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

interface SpecFieldsProps {
  capabilities: Capabilities | null;
  value: PrintSpecification;
  onChange: (spec: PrintSpecification) => void;
  /** Show the Portrait/Landscape control — it only affects picture files. */
  showOrientation?: boolean;
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

export default function SpecFields({
  capabilities, value, onChange, showOrientation = true,
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

  return (
    <div className="space-y-4">
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

      <div className="space-y-1.5">
        <Label>Paper type</Label>
        <RadioGroup
          value={value.media_type}
          onValueChange={(v) => update("media_type", v)}
          className="grid grid-cols-2 gap-2"
        >
          {(typesForSize.length > 0 ? typesForSize : [{ paperType: "pt_plainpaper" }]).map((t) => (
            <div key={t.paperType} className="flex items-center space-x-2 rounded-md border p-2.5">
              <RadioGroupItem value={t.paperType} id={`pt-${t.paperType}`} />
              <Label htmlFor={`pt-${t.paperType}`} className="cursor-pointer font-normal">
                {paperTypeLabel(t.paperType)}
              </Label>
            </div>
          ))}
        </RadioGroup>
      </div>

      <div className="space-y-1.5">
        <Label>Color</Label>
        <RadioGroup
          value={value.color_mode}
          onValueChange={(v) => update("color_mode", v as "color" | "mono")}
          className="flex gap-2"
        >
          <div className="flex items-center space-x-2 rounded-md border p-2.5">
            <RadioGroupItem value="mono" id="cm-mono" />
            <Label htmlFor="cm-mono" className="cursor-pointer font-normal">Black & white</Label>
          </div>
          <div className="flex items-center space-x-2 rounded-md border p-2.5">
            <RadioGroupItem value="color" id="cm-color" />
            <Label htmlFor="cm-color" className="cursor-pointer font-normal">Color</Label>
          </div>
        </RadioGroup>
      </div>

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

      {showOrientation && (
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
      )}

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

      <div className="space-y-1.5">
        <Label htmlFor="instructions">Special instructions (optional)</Label>
        <Textarea
          id="instructions"
          placeholder="e.g. 'print the first 5 pages in color, rest in black & white'"
          value={value.free_text_instructions ?? ""}
          onChange={(e) => update("free_text_instructions", e.target.value)}
          rows={3}
        />
      </div>

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
        {advanced && (
          <div className="space-y-4 border-t p-3">
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
          </div>
        )}
      </div>
    </div>
  );
}
