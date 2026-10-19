import * as React from "react";
import { getSupportedTimeZones } from "@/features/timezone/lib/timezone-options";

export const TIMEZONE_SEARCH_PLACEHOLDER =
  "Search timezone (e.g. America/New_York)";

export const normalizeTimezoneSearchValue = (value: string) =>
  value
    .toLowerCase()
    .replaceAll(/[_/.-]+/g, " ")
    .replaceAll(/\s+/g, " ")
    .trim();

export const shouldStopMenuTypeaheadKey = (key: string) =>
  key.length === 1 || key === "Backspace" || key === "Delete";

type SearchableTimeZone = {
  timeZone: string;
  normalized: string;
};

let timeZoneSearchIndexCache: {
  supportedTimeZones: string[];
  searchableTimeZones: SearchableTimeZone[];
} | null = null;

const getTimeZoneSearchIndex = () => {
  if (timeZoneSearchIndexCache) return timeZoneSearchIndexCache;

  const supportedTimeZones = getSupportedTimeZones();
  const searchableTimeZones = supportedTimeZones.map(timeZone => ({
    timeZone,
    normalized: normalizeTimezoneSearchValue(timeZone),
  }));

  timeZoneSearchIndexCache = {
    supportedTimeZones,
    searchableTimeZones,
  };

  return timeZoneSearchIndexCache;
};

export const useFilteredTimeZones = (searchValue: string) => {
  const { supportedTimeZones, searchableTimeZones } = React.useMemo(
    () => getTimeZoneSearchIndex(),
    []
  );

  const normalizedSearchValue = React.useMemo(
    () => normalizeTimezoneSearchValue(searchValue),
    [searchValue]
  );

  const filteredTimeZones = React.useMemo(() => {
    if (normalizedSearchValue.length === 0) return supportedTimeZones;

    const matches: string[] = [];

    for (const { timeZone, normalized } of searchableTimeZones) {
      if (!normalized.includes(normalizedSearchValue)) continue;
      matches.push(timeZone);
    }

    return matches;
  }, [normalizedSearchValue, searchableTimeZones, supportedTimeZones]);

  return {
    filteredTimeZones,
    normalizedSearchValue,
  };
};
