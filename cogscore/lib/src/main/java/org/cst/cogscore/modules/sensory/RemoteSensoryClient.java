package org.cst.cogscore.modules.sensory.remote;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class RemoteSensoryClient {

    private final String baseUrl;
    private final HttpClient client;

    public RemoteSensoryClient(String baseUrl) {
        this.baseUrl = stripTrailingSlash(baseUrl);
        this.client = HttpClient.newHttpClient();
    }

    private static String stripTrailingSlash(String value) {
        if (value == null) return "";
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    public void health() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/health"))
                .GET()
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("Remote health failed: " + response.statusCode() + " " + response.body());
        }
    }

    public void reset(int episode) throws IOException, InterruptedException {
        String json = "{\"benchmark\":\"sensory_buffer\",\"episode\":" + episode + "}";

        postJson("/reset", json);
    }

    public void sendStimulus(
            int episode,
            int trial,
            long delayMs,
            int width,
            int height,
            List<Float> frame
    ) throws IOException, InterruptedException {
        StringBuilder sb = new StringBuilder();

        sb.append("{");
        sb.append("\"benchmark\":\"sensory_buffer\",");
        sb.append("\"episode\":").append(episode).append(",");
        sb.append("\"trial\":").append(trial).append(",");
        sb.append("\"delay_ms\":").append(delayMs).append(",");
        sb.append("\"width\":").append(width).append(",");
        sb.append("\"height\":").append(height).append(",");
        sb.append("\"channels\":3,");
        sb.append("\"encoding\":\"rgb_float_0_255\",");
        sb.append("\"frame\":[");

        for (int i = 0; i < frame.size(); i++) {
            if (i > 0) sb.append(",");
            float value = frame.get(i);
            if (!Float.isFinite(value)) value = 0.0f;
            sb.append(String.format(Locale.US, "%.6f", value));
        }

        sb.append("]}");

        postJson("/sensory/stimulus", sb.toString());
    }

    public List<Float> readoutPatch(
            int episode,
            int trial,
            long delayMs,
            int x0,
            int y0,
            int size
    ) throws IOException, InterruptedException {
        String json =
                "{"
                        + "\"benchmark\":\"sensory_buffer\","
                        + "\"episode\":" + episode + ","
                        + "\"trial\":" + trial + ","
                        + "\"delay_ms\":" + delayMs + ","
                        + "\"cue\":{"
                        + "\"type\":\"patch\","
                        + "\"x0\":" + x0 + ","
                        + "\"y0\":" + y0 + ","
                        + "\"size\":" + size
                        + "}"
                        + "}";

        String body = postJson("/sensory/readout", json);

        return parsePatchArray(body);
    }

    public void close() throws IOException, InterruptedException {
        postJson("/close", "{}");
    }

    private String postJson(String path, String json) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("Remote POST failed at " + path + ": " + response.statusCode() + " " + response.body());
        }

        return response.body();
    }

    private List<Float> parsePatchArray(String json) throws IOException {
        int patchKey = json.indexOf("\"patch\"");
        if (patchKey < 0) {
            throw new IOException("Remote response does not contain patch: " + json);
        }

        int start = json.indexOf("[", patchKey);
        int end = json.indexOf("]", start);

        if (start < 0 || end < 0 || end <= start) {
            throw new IOException("Could not parse patch array: " + json);
        }

        String content = json.substring(start + 1, end).trim();
        List<Float> values = new ArrayList<>();

        if (content.isEmpty()) {
            return values;
        }

        String[] parts = content.split(",");

        for (String part : parts) {
            try {
                values.add(Float.parseFloat(part.trim()));
            } catch (NumberFormatException exc) {
                values.add(0.0f);
            }
        }

        return values;
    }
}
