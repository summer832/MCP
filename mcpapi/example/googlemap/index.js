#!/usr/bin/env node
"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const index_js_1 = require("@modelcontextprotocol/sdk/server/index.js");
const stdio_js_1 = require("@modelcontextprotocol/sdk/server/stdio.js");
const types_js_1 = require("@modelcontextprotocol/sdk/types.js");
const node_fetch_1 = __importDefault(require("node-fetch"));
function getApiKey() {
    const apiKey = process.env.GOOGLE_MAPS_API_KEY;
    if (!apiKey) {
        console.error("GOOGLE_MAPS_API_KEY environment variable is not set");
        process.exit(1);
    }
    return apiKey;
}
const GOOGLE_MAPS_API_KEY = getApiKey();
// Tool definitions
const GEOCODE_TOOL = {
    name: "maps_geocode",
    description: "Convert an address into geographic coordinates",
    inputSchema: {
        type: "object",
        properties: {
            address: {
                type: "string",
                description: "The address to geocode"
            }
        },
        required: ["address"]
    }
};
const REVERSE_GEOCODE_TOOL = {
    name: "maps_reverse_geocode",
    description: "Convert coordinates into an address",
    inputSchema: {
        type: "object",
        properties: {
            latitude: {
                type: "number",
                description: "Latitude coordinate"
            },
            longitude: {
                type: "number",
                description: "Longitude coordinate"
            }
        },
        required: ["latitude", "longitude"]
    }
};
const SEARCH_PLACES_TOOL = {
    name: "maps_search_places",
    description: "Search for places using Google Places API",
    inputSchema: {
        type: "object",
        properties: {
            query: {
                type: "string",
                description: "Search query"
            },
            location: {
                type: "object",
                properties: {
                    latitude: { type: "number" },
                    longitude: { type: "number" }
                },
                description: "Optional center point for the search"
            },
            radius: {
                type: "number",
                description: "Search radius in meters (max 50000)"
            }
        },
        required: ["query"]
    }
};
const PLACE_DETAILS_TOOL = {
    name: "maps_place_details",
    description: "Get detailed information about a specific place",
    inputSchema: {
        type: "object",
        properties: {
            place_id: {
                type: "string",
                description: "The place ID to get details for"
            }
        },
        required: ["place_id"]
    }
};
const DISTANCE_MATRIX_TOOL = {
    name: "maps_distance_matrix",
    description: "Calculate travel distance and time for multiple origins and destinations",
    inputSchema: {
        type: "object",
        properties: {
            origins: {
                type: "array",
                items: { type: "string" },
                description: "Array of origin addresses or coordinates"
            },
            destinations: {
                type: "array",
                items: { type: "string" },
                description: "Array of destination addresses or coordinates"
            },
            mode: {
                type: "string",
                description: "Travel mode (driving, walking, bicycling, transit)",
                enum: ["driving", "walking", "bicycling", "transit"]
            }
        },
        required: ["origins", "destinations"]
    }
};
const ELEVATION_TOOL = {
    name: "maps_elevation",
    description: "Get elevation data for locations on the earth",
    inputSchema: {
        type: "object",
        properties: {
            locations: {
                type: "array",
                items: {
                    type: "object",
                    properties: {
                        latitude: { type: "number" },
                        longitude: { type: "number" }
                    },
                    required: ["latitude", "longitude"]
                },
                description: "Array of locations to get elevation for"
            }
        },
        required: ["locations"]
    }
};
const DIRECTIONS_TOOL = {
    name: "maps_directions",
    description: "Get directions between two points",
    inputSchema: {
        type: "object",
        properties: {
            origin: {
                type: "string",
                description: "Starting point address or coordinates"
            },
            destination: {
                type: "string",
                description: "Ending point address or coordinates"
            },
            mode: {
                type: "string",
                description: "Travel mode (driving, walking, bicycling, transit)",
                enum: ["driving", "walking", "bicycling", "transit"]
            }
        },
        required: ["origin", "destination"]
    }
};
const MAPS_TOOLS = [
    GEOCODE_TOOL,
    REVERSE_GEOCODE_TOOL,
    SEARCH_PLACES_TOOL,
    PLACE_DETAILS_TOOL,
    DISTANCE_MATRIX_TOOL,
    ELEVATION_TOOL,
    DIRECTIONS_TOOL,
];
// API handlers
function handleGeocode(address) {
    return __awaiter(this, void 0, void 0, function* () {
        const url = new URL("https://maps.googleapis.com/maps/api/geocode/json");
        url.searchParams.append("address", address);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Geocoding failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        location: data.results[0].geometry.location,
                        formatted_address: data.results[0].formatted_address,
                        place_id: data.results[0].place_id
                    }, null, 2)
                }],
            isError: false
        };
    });
}
function handleReverseGeocode(latitude, longitude) {
    return __awaiter(this, void 0, void 0, function* () {
        const url = new URL("https://maps.googleapis.com/maps/api/geocode/json");
        url.searchParams.append("latlng", `${latitude},${longitude}`);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Reverse geocoding failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        formatted_address: data.results[0].formatted_address,
                        place_id: data.results[0].place_id,
                        address_components: data.results[0].address_components
                    }, null, 2)
                }],
            isError: false
        };
    });
}
function handlePlaceSearch(query, location, radius) {
    return __awaiter(this, void 0, void 0, function* () {
        const url = new URL("https://maps.googleapis.com/maps/api/place/textsearch/json");
        url.searchParams.append("query", query);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        if (location) {
            url.searchParams.append("location", `${location.latitude},${location.longitude}`);
        }
        if (radius) {
            url.searchParams.append("radius", radius.toString());
        }
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Place search failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        places: data.results.map((place) => ({
                            name: place.name,
                            formatted_address: place.formatted_address,
                            location: place.geometry.location,
                            place_id: place.place_id,
                            rating: place.rating,
                            types: place.types
                        }))
                    }, null, 2)
                }],
            isError: false
        };
    });
}
function handlePlaceDetails(place_id) {
    return __awaiter(this, void 0, void 0, function* () {
        const url = new URL("https://maps.googleapis.com/maps/api/place/details/json");
        url.searchParams.append("place_id", place_id);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Place details request failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        name: data.result.name,
                        formatted_address: data.result.formatted_address,
                        location: data.result.geometry.location,
                        formatted_phone_number: data.result.formatted_phone_number,
                        website: data.result.website,
                        rating: data.result.rating,
                        reviews: data.result.reviews,
                        opening_hours: data.result.opening_hours
                    }, null, 2)
                }],
            isError: false
        };
    });
}
function handleDistanceMatrix(origins_1, destinations_1) {
    return __awaiter(this, arguments, void 0, function* (origins, destinations, mode = "driving") {
        const url = new URL("https://maps.googleapis.com/maps/api/distancematrix/json");
        url.searchParams.append("origins", origins.join("|"));
        url.searchParams.append("destinations", destinations.join("|"));
        url.searchParams.append("mode", mode);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Distance matrix request failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        origin_addresses: data.origin_addresses,
                        destination_addresses: data.destination_addresses,
                        results: data.rows.map((row) => ({
                            elements: row.elements.map((element) => ({
                                status: element.status,
                                duration: element.duration,
                                distance: element.distance
                            }))
                        }))
                    }, null, 2)
                }],
            isError: false
        };
    });
}
function handleElevation(locations) {
    return __awaiter(this, void 0, void 0, function* () {
        const url = new URL("https://maps.googleapis.com/maps/api/elevation/json");
        const locationString = locations
            .map((loc) => `${loc.latitude},${loc.longitude}`)
            .join("|");
        url.searchParams.append("locations", locationString);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Elevation request failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        results: data.results.map((result) => ({
                            elevation: result.elevation,
                            location: result.location,
                            resolution: result.resolution
                        }))
                    }, null, 2)
                }],
            isError: false
        };
    });
}
function handleDirections(origin_1, destination_1) {
    return __awaiter(this, arguments, void 0, function* (origin, destination, mode = "driving") {
        const url = new URL("https://maps.googleapis.com/maps/api/directions/json");
        url.searchParams.append("origin", origin);
        url.searchParams.append("destination", destination);
        url.searchParams.append("mode", mode);
        url.searchParams.append("key", GOOGLE_MAPS_API_KEY);
        const response = yield (0, node_fetch_1.default)(url.toString());
        const data = yield response.json();
        if (data.status !== "OK") {
            return {
                content: [{
                        type: "text",
                        text: `Directions request failed: ${data.error_message || data.status}`
                    }],
                isError: true
            };
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        routes: data.routes.map((route) => ({
                            summary: route.summary,
                            distance: route.legs[0].distance,
                            duration: route.legs[0].duration,
                            steps: route.legs[0].steps.map((step) => ({
                                instructions: step.html_instructions,
                                distance: step.distance,
                                duration: step.duration,
                                travel_mode: step.travel_mode
                            }))
                        }))
                    }, null, 2)
                }],
            isError: false
        };
    });
}
// Server setup
const server = new index_js_1.Server({
    name: "mcp-server/google-maps",
    version: "0.1.0",
}, {
    capabilities: {
        tools: {},
    },
});
// Set up request handlers
server.setRequestHandler(types_js_1.ListToolsRequestSchema, () => __awaiter(void 0, void 0, void 0, function* () {
    return ({
        tools: MAPS_TOOLS,
    });
}));
server.setRequestHandler(types_js_1.CallToolRequestSchema, (request) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        switch (request.params.name) {
            case "maps_geocode": {
                const { address } = request.params.arguments;
                return yield handleGeocode(address);
            }
            case "maps_reverse_geocode": {
                const { latitude, longitude } = request.params.arguments;
                return yield handleReverseGeocode(latitude, longitude);
            }
            case "maps_search_places": {
                const { query, location, radius } = request.params.arguments;
                return yield handlePlaceSearch(query, location, radius);
            }
            case "maps_place_details": {
                const { place_id } = request.params.arguments;
                return yield handlePlaceDetails(place_id);
            }
            case "maps_distance_matrix": {
                const { origins, destinations, mode } = request.params.arguments;
                return yield handleDistanceMatrix(origins, destinations, mode);
            }
            case "maps_elevation": {
                const { locations } = request.params.arguments;
                return yield handleElevation(locations);
            }
            case "maps_directions": {
                const { origin, destination, mode } = request.params.arguments;
                return yield handleDirections(origin, destination, mode);
            }
            default:
                return {
                    content: [{
                            type: "text",
                            text: `Unknown tool: ${request.params.name}`
                        }],
                    isError: true
                };
        }
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: `Error: ${error instanceof Error ? error.message : String(error)}`
                }],
            isError: true
        };
    }
}));
function runServer() {
    return __awaiter(this, void 0, void 0, function* () {
        const transport = new stdio_js_1.StdioServerTransport();
        yield server.connect(transport);
        console.error("Google Maps MCP Server running on stdio");
    });
}
runServer().catch((error) => {
    console.error("Fatal error running server:", error);
    process.exit(1);
});
