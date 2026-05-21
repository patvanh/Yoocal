/**
 * Curated venue list — preserved exactly from the original venues.html.
 *
 * Each venue's `name` is used to match against events in events.json
 * (event.location). The match is case-insensitive AND uses a contains check —
 * so "Egyptian Theatre" matches event.location values like:
 *   - "Egyptian Theatre"
 *   - "The Egyptian Theatre, Park City"
 *   - "Egyptian Theatre · Main Street"
 *
 * Add additional matching strings via `matchAliases` if you find venues
 * where the event's location field uses a different wording.
 */

export type VenueTag = "music" | "arts" | "food" | "outdoor" | "family" | "sports" | "community" | "wellness";

export type Venue = {
  name: string;
  emoji: string;
  address: string;
  tags: VenueTag[];
  desc: string;
  /** Optional extra strings to match against event.location for this venue. */
  matchAliases?: string[];
};

export const VENUES_BY_CITY: Record<"parkcity" | "elkhartlake" | "heber" | "jackson", Venue[]> = {
  parkcity: [
    {
      name: "Egyptian Theatre",
      emoji: "🎭",
      address: "328 Main St, Park City, UT 84060",
      tags: ["arts", "music"],
      desc: "Park City's landmark 1926 theatre on Historic Main Street. Hosts world-class concerts, comedy shows, film screenings, and theatrical productions year-round. Home to the Sundance Film Festival.",
    },
    {
      name: "The Spur Bar and Grill",
      emoji: "🎸",
      address: "352 Main St, Park City, UT 84060",
      tags: ["music", "food"],
      desc: "Park City's premier live music bar on Main Street. Nightly live performances from local and touring acts, cold beers, and a lively crowd seven nights a week.",
      matchAliases: ["Spur Bar", "The Spur"],
    },
    {
      name: "Deer Valley Resort",
      emoji: "⛷️",
      address: "2250 Deer Valley Dr S, Park City, UT 84060",
      tags: ["outdoor", "music"],
      desc: "World-class ski resort hosting summer concerts, festivals, and outdoor events. The Snow Park Amphitheater draws major acts every summer season for outdoor performances under the stars.",
      matchAliases: ["Deer Valley", "Snow Park Amphitheater"],
    },
    {
      name: "Kimball Arts Center",
      emoji: "🖼️",
      address: "638 Park Ave, Park City, UT 84060",
      tags: ["arts"],
      desc: "Park City's community arts hub. Home to galleries, studio spaces, classes, and the annual Kimball Arts Festival — one of Utah's premier outdoor arts events each August.",
      matchAliases: ["Kimball Arts"],
    },
    {
      name: "High West Distillery",
      emoji: "🥃",
      address: "703 Park Ave, Park City, UT 84060",
      tags: ["food"],
      desc: "America's first ski-in distillery. Award-winning whiskeys, a full restaurant, and regular tasting events and special releases. A Park City institution for whiskey lovers.",
      matchAliases: ["High West"],
    },
    {
      name: "Park City Library",
      emoji: "📚",
      address: "1255 Park Ave, Park City, UT 84060",
      tags: ["family", "arts"],
      desc: "More than a library — a community hub hosting lectures, film screenings, kids programming, author talks, and free community events throughout the year.",
    },
    {
      name: "Swaner EcoCenter",
      emoji: "🌿",
      address: "1258 Center Dr, Park City, UT 84098",
      tags: ["outdoor", "family"],
      desc: "Nature preserve and education center at Kimball Junction. Hosts nature programs, Sunday crafts, guided walks, and family-friendly activities in a stunning wetland setting.",
      matchAliases: ["Swaner"],
    },
    {
      name: "Park City Senior Center",
      emoji: "🎵",
      address: "1361 Woodside Ave, Park City, UT 84060",
      tags: ["community", "music"],
      desc: "Community center hosting Mountain Town Music free outdoor concerts on Wednesday afternoons throughout the summer. A local favorite for picnic-style live music.",
      matchAliases: ["1361 Woodside Ave", "1361 Woodside"],
    },
    {
      name: "Eccles Center for the Performing Arts",
      emoji: "🎼",
      address: "1750 Kearns Blvd, Park City, UT 84060",
      tags: ["arts", "music"],
      desc: "Park City's premier performing arts venue with a 1,100-seat main stage. Home to Park City Institute's world-class speaker and performance series, orchestra, and Broadway touring productions.",
      matchAliases: ["Eccles Center", "Eccles"],
    },
    {
      name: "No Name Saloon",
      emoji: "🍺",
      address: "447 Main St, Park City, UT 84060",
      tags: ["food"],
      desc: "A legendary dive bar on Historic Main Street. Buffalo burgers, cold beers, and a rooftop deck with mountain views. No frills, no pretense — just good times on Main Street.",
    },
    {
      name: "Park City Mountain Resort",
      emoji: "🏔️",
      address: "1310 Lowell Ave, Park City, UT 84060",
      tags: ["outdoor", "sports"],
      desc: "Utah's largest ski resort with 7,300 acres of terrain. Summer brings lift-served mountain biking, hiking, concerts, and the mountain coaster. Year-round activities for all ages.",
      matchAliases: ["Park City Mountain", "PCMR"],
    },
    {
      name: "Jordanelle State Park",
      emoji: "🚣",
      address: "UT-319, Heber City, UT 84032",
      tags: ["outdoor", "sports"],
      desc: "Stunning reservoir 15 minutes from Park City. Swimming, kayaking, paddleboarding, and camping in summer. Hosts open water swimming events and triathlon competitions.",
      matchAliases: ["Jordanelle"],
    },
    {
      name: "Park City Film Series",
      emoji: "🎬",
      address: "1255 Park Ave, Park City, UT 84060",
      tags: ["arts", "family"],
      desc: "Year-round independent and foreign film screenings. Weekly films, special screenings, and filmmaker Q&As in an intimate theater setting. Beloved by Park City's arts community.",
      matchAliases: ["Park City Film"],
    },
  ],
  elkhartlake: [
    {
      name: "Road America",
      emoji: "🏁",
      address: "N7390 US-12, Elkhart Lake, WI 53020",
      tags: ["sports", "outdoor"],
      desc: "One of America's greatest road racing circuits. A 4-mile, 14-turn track set amid rolling Wisconsin countryside. Hosts IndyCar, NASCAR, IMSA, and MotoAmerica events drawing tens of thousands of fans each summer.",
    },
    {
      name: "Siebkens Resort",
      emoji: "🍺",
      address: "284 S Lake St, Elkhart Lake, WI 53020",
      tags: ["food", "music"],
      desc: "A legendary lakeside tavern and resort that has been the heart of Elkhart Lake's social scene since 1916. Live music, cold drinks, and a lively crowd especially during race weekends.",
      matchAliases: ["Siebkens", "Stop-Inn Tavern", "The Elk Room"],
    },
    {
      name: "Elkhart Lake Village Park",
      emoji: "🌳",
      address: "Village Park, Elkhart Lake, WI 53020",
      tags: ["outdoor", "family", "community"],
      desc: "The heart of the village. Hosts summer concerts, community events, festivals, and gatherings on the shores of Elkhart Lake. A gathering place for locals and visitors throughout the warm months.",
      matchAliases: ["Village Park", "Village Square"],
    },
    {
      name: "The Paddock Club",
      emoji: "🥂",
      address: "Elkhart Lake, WI 53020",
      tags: ["food", "sports"],
      desc: "A classic Elkhart Lake dining spot popular with the racing crowd. Great food, local atmosphere, and a front-row seat to the race weekend energy that takes over the village each summer.",
      matchAliases: ["Paddock Club"],
    },
    {
      name: "Osthoff Resort",
      emoji: "🏨",
      address: "101 Osthoff Ave, Elkhart Lake, WI 53020",
      tags: ["outdoor", "family", "wellness"],
      desc: "A premier lakefront resort on Elkhart Lake offering cooking classes, spa services, outdoor activities, and year-round events. The area's top destination for leisure and special occasions.",
      matchAliases: ["Osthoff", "The Osthoff", "Lola's on the Lake"],
    },
    {
      name: "Quit Qui Oc Golf Course",
      emoji: "⛳",
      address: "700 County Rd P, Elkhart Lake, WI 53020",
      tags: ["sports", "outdoor"],
      desc: "A scenic public golf course in the heart of the Kettle Moraine. Hosts local tournaments, fundraisers, and community events throughout the golf season.",
      matchAliases: ["Quit Qui Oc"],
    },
  ],
  heber: [
    {
      name: "Heber Valley Railroad",
      emoji: "🚂",
      address: "450 S 600 W, Heber City, UT 84032",
      tags: ["family", "community"],
      desc: "Historic train excursions through Heber Valley on a real steam railroad. Dinner trains, holiday rides, North Pole Express, and seasonal special events all year long.",
      matchAliases: ["Heber Valley Railroad", "Heber Railroad"],
    },
    {
      name: "Soldier Hollow",
      emoji: "🎿",
      address: "1370 W Soldier Hollow Ln, Midway, UT 84049",
      tags: ["sports", "outdoor", "family"],
      desc: "2002 Olympic biathlon and cross-country venue. Tubing in winter, hiking and biking in summer, plus the famous Soldier Hollow Classic sheepdog championships every Labor Day weekend.",
      matchAliases: ["Soldier Hollow Nordic Center"],
    },
    {
      name: "Deer Creek Reservoir",
      emoji: "🚣",
      address: "Deer Creek State Park, UT-189, Heber City, UT 84032",
      tags: ["outdoor", "sports", "family"],
      desc: "Beautiful state-park reservoir between Heber and Provo Canyon. Boating, paddleboarding, swimming, kayaking, and fishing with Wasatch views — calmer than Jordanelle.",
      matchAliases: ["Deer Creek State Park", "Deer Creek"],
    },
    {
      name: "Homestead Crater",
      emoji: "🌋",
      address: "700 Homestead Dr, Midway, UT 84049",
      tags: ["wellness", "family", "outdoor"],
      desc: "A geothermal hot spring inside a 55-foot limestone dome. Swimming, snorkeling, and SCUBA in 90°F mineral water year-round — one of the most unique experiences in Utah.",
      matchAliases: ["Homestead Resort"],
    },
    {
      name: "Heber Valley Cheese & Dairy",
      emoji: "🐄",
      address: "920 N 1300 W, Heber City, UT 84032",
      tags: ["family", "food", "community"],
      desc: "Working family dairy offering daily farm tours, fresh ice cream, cheese tastings, and barn visits. A hands-on look at Heber Valley's farming heritage that kids especially love.",
      matchAliases: ["Heber Valley Artisan Cheese", "Heber Valley Cheese", "Dairy Farm Tour"],
    },
    {
      name: "Midway Town Hall",
      emoji: "🏛️",
      address: "75 N 100 W, Midway, UT 84049",
      tags: ["community", "arts", "family"],
      desc: "Heart of historic Midway, hosting community events, town meetings, Swiss Days celebrations every Labor Day weekend, and seasonal programs throughout the year.",
      matchAliases: ["Midway"],
    },
  ],
  jackson: [
    {
      name: "Grand Teton Music Festival",
      emoji: "🎼",
      address: "Walk Festival Hall, Teton Village, WY 83025",
      tags: ["music", "community"],
      desc: "World-class summer classical festival at the foot of the Tetons. Seven weeks of Festival Orchestra concerts, Gateway Series headliners (Punch Brothers, The King's Singers), Open Rehearsals, and free Musical Adventures programming around the valley.",
      matchAliases: ["Grand Teton Music Festival", "GTMF", "Walk Festival Hall"],
    },
    {
      name: "Center for the Arts",
      emoji: "🎭",
      address: "240 S Glenwood St, Jackson, WY 83001",
      tags: ["music", "community"],
      desc: "Jackson Hole's downtown arts hub. Theater, dance, concerts, films, and year-round community programming. Home stage for the Center Series and dozens of local arts groups.",
      matchAliases: ["Center for the Arts", "Center for the Arts Theater", "JH Center for the Arts"],
    },
    {
      name: "Snow King Mountain",
      emoji: "🎿",
      address: "402 E Snow King Ave, Jackson, WY 83001",
      tags: ["sports", "outdoor", "music"],
      desc: "Jackson's in-town mountain — affectionately the Town Hill. Skiing in winter, alpine slide and bike park in summer, plus the King Concerts series under the chairlifts on warm-weather nights.",
      matchAliases: ["Snow King", "Snow King Resort", "Snow King Mountain"],
    },
    {
      name: "Jackson Hole Mountain Resort",
      emoji: "🏔️",
      address: "3395 Cody Ln, Teton Village, WY 83025",
      tags: ["sports", "outdoor", "food"],
      desc: "The big one — JHMR at Teton Village. World-renowned skiing in winter, gondola rides and hiking in summer, plus the Jackson Hole Food & Wine festival and special events throughout the year.",
      matchAliases: ["Jackson Hole Mountain Resort", "JHMR", "Teton Village"],
    },
    {
      name: "Teton County Fairgrounds",
      emoji: "🎪",
      address: "305 W Snow King Ave, Jackson, WY 83001",
      tags: ["family", "community"],
      desc: "Home of the Teton County Fair every July plus the summer-long Jackson Hole Rodeo. Cowboy culture, livestock shows, demolition derby, and a midway that brings the whole valley together.",
      matchAliases: ["Teton County Fairgrounds", "Fairgrounds", "Jackson Hole Rodeo"],
    },
    {
      name: "Grand Teton National Park",
      emoji: "🏕️",
      address: "Moose, WY 83012",
      tags: ["outdoor", "family"],
      desc: "310,000 acres of glacial lakes, alpine meadows, and the most dramatic skyline in the lower 48. Hiking, climbing, wildlife viewing, and ranger programs right outside Jackson.",
      matchAliases: ["Grand Teton", "Grand Teton National Park", "GTNP"],
    },
    {
      name: "National Elk Refuge",
      emoji: "🦌",
      address: "532 N Cache St, Jackson, WY 83001",
      tags: ["outdoor", "family", "wellness"],
      desc: "Wintering ground for thousands of elk just north of town. Famous horse-drawn sleigh rides take visitors out into the herd December through March — a true Jackson Hole experience.",
      matchAliases: ["National Elk Refuge", "Elk Refuge"],
    },
    {
      name: "Murie Ranch",
      emoji: "🌲",
      address: "1 Murie Ranch Rd, Moose, WY 83012",
      tags: ["outdoor", "community"],
      desc: "Historic dude ranch turned conservation center inside Grand Teton National Park. Hosts intimate On the Road chamber concerts from the Grand Teton Music Festival, plus lectures and conservation programming.",
      matchAliases: ["Murie Ranch", "Murie Center"],
    },
  ],
};

/** Human-readable label for a tag. */
export const TAG_LABELS: Record<VenueTag, string> = {
  music: "Music",
  arts: "Arts",
  food: "Food & Drink",
  outdoor: "Outdoor",
  family: "Family",
  sports: "Sports",
  community: "Community",
  wellness: "Wellness",
};

/** Order tags appear in the filter chips bar. */
export const TAG_ORDER: VenueTag[] = [
  "music",
  "arts",
  "food",
  "outdoor",
  "family",
  "sports",
  "community",
  "wellness",
];

/**
 * Case-insensitive contains match between an event's location string and a
 * venue (matches against venue name AND any aliases).
 */
export function eventMatchesVenue(eventLocation: string | undefined | null, venue: Venue): boolean {
  if (!eventLocation) return false;
  const loc = eventLocation.toLowerCase();
  const candidates = [venue.name, ...(venue.matchAliases ?? [])];
  return candidates.some((c) => loc.includes(c.toLowerCase()));
}
