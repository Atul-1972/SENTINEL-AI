import { useRef, useState } from "react";
import { api } from "../services/api";
import { MAX_FILE_BYTES, parseFlowCsv } from "../services/csv";

export function useAnalysis(featureNames, refresh) {
  const [dataset, setDataset] = useState(null);
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [parsing, setParsing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [source, setSource] = useState("historical");
  const [finished, setFinished] = useState(false);
  const [stopping, setStopping] = useState(false);
  const busyRef = useRef(false);
  const stopRef = useRef(false);

  async function loadText(text, name) {
    if (busyRef.current) return;
    setParsing(true);
    setError("");
    setResults([]);
    setFinished(false);
    setProgress(0);
    try {
      const parsed = parseFlowCsv(text, featureNames);
      setDataset({ ...parsed, name });
    } catch (err) {
      setDataset(null);
      setError(err.message);
    } finally {
      setParsing(false);
    }
  }
  async function loadFile(file) {
    if (!file || busyRef.current) return;
    setDataset(null);
    setResults([]);
    setProgress(0);
    setFinished(false);
    if (file.size > MAX_FILE_BYTES) {
      setError("Choose a CSV below 25 MB. Use the 20,000-row prepared subset.");
      return;
    }
    setParsing(true);
    try {
      await loadText(await file.text(), file.name);
    } catch (err) {
      setError(`Could not read this file: ${err.message}`);
    } finally {
      setParsing(false);
    }
  }
  async function loadExample() {
    setError("");
    setParsing(true);
    try {
      const response = await fetch("/demo-flows.csv");
      if (!response.ok) throw new Error("Historical example is unavailable.");
      await loadText(
        await response.text(),
        "CIC-IDS2017 · historical demo.csv",
      );
      setSource("historical");
    } catch (err) {
      setError(err.message);
    } finally {
      setParsing(false);
    }
  }
  async function analyze() {
    if (!dataset || busyRef.current) return;
    busyRef.current = true;
    stopRef.current = false;
    const start = progress < dataset.records.length ? progress : 0;
    let completed = start;
    setBusy(true);
    setError("");
    setFinished(false);
    setStopping(false);
    if (!start) {
      setResults([]);
      setProgress(0);
    }
    try {
      for (
        let offset = start;
        offset < dataset.records.length;
        offset += 1000
      ) {
        if (stopRef.current) break;
        const records = dataset.records.slice(offset, offset + 1000);
        const response = await api.predict(
          records.map((row) => ({ features: row.features, source })),
        );
        const next = response.results.map((result, index) => ({
          ...result,
          input_row: records[index].row,
          known_label: records[index].knownLabel,
        }));
        setResults((prev) => [...prev, ...next]);
        setProgress(offset + records.length);
        completed = offset + records.length;
      }
      setFinished(completed === dataset.records.length);
    } catch (err) {
      setError(
        `${err.message} Completed batches remain saved; avoid resubmitting them unintentionally.`,
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
      await refresh();
    }
  }
  return {
    dataset,
    results,
    error,
    parsing,
    busy,
    progress,
    source,
    finished,
    stopping,
    setSource,
    loadFile,
    loadExample,
    analyze,
    stop: () => {
      stopRef.current = true;
      setStopping(true);
    },
    clear: () => {
      if (!busyRef.current) {
        setDataset(null);
        setResults([]);
        setError("");
        setProgress(0);
        setFinished(false);
      }
    },
  };
}
