import { type FormEvent, useState } from "react";

import type { ResearchInput } from "../types";

interface Props {
  onSubmit: (input: ResearchInput) => void;
  busy: boolean;
}

export default function ResearchForm({ onSubmit, busy }: Props) {
  const [company, setCompany] = useState("");
  const [website, setWebsite] = useState("");
  const [ticker, setTicker] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const name = company.trim();
    if (name === "") return;
    onSubmit({
      company: name,
      website: website.trim() || undefined,
      ticker: ticker.trim() || undefined,
    });
  };

  return (
    <form className="research-form" onSubmit={handleSubmit}>
      <label>
        Company name
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="Acme Robotics"
          required
          maxLength={200}
        />
      </label>
      <label>
        Website <span className="optional">(optional)</span>
        <input
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
          placeholder="https://acme-robotics.com"
          type="url"
        />
      </label>
      <label>
        Ticker <span className="optional">(optional)</span>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="ACME"
          maxLength={10}
        />
      </label>
      <button type="submit" disabled={busy || company.trim() === ""}>
        {busy ? "Researching…" : "Research"}
      </button>
    </form>
  );
}
