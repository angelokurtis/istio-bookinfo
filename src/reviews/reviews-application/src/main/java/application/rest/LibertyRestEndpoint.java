/*******************************************************************************
 * Copyright (c) 2017 Istio Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *******************************************************************************/
package application.rest;

import java.io.PrintWriter;
import java.io.StringReader;
import java.io.StringWriter;
import java.time.LocalDateTime;
import javax.json.Json;
import javax.json.JsonObject;
import javax.json.JsonReader;
import javax.ws.rs.GET;
import javax.ws.rs.Path;
import javax.ws.rs.PathParam;
import javax.ws.rs.ProcessingException;
import javax.ws.rs.client.Client;
import javax.ws.rs.client.ClientBuilder;
import javax.ws.rs.client.Invocation;
import javax.ws.rs.client.WebTarget;
import javax.ws.rs.core.Application;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.HttpHeaders;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;

@Path("/")
public class LibertyRestEndpoint extends Application {

    private final static Boolean ratings_enabled = Boolean.valueOf(System.getenv("ENABLE_RATINGS"));
    private final static String star_color = System.getenv("STAR_COLOR") == null ? "black" : System.getenv("STAR_COLOR");
    private final static String services_domain = System.getenv("SERVICES_DOMAIN") == null ? "" : ("." + System.getenv("SERVICES_DOMAIN"));
    private final static String ratings_hostname = System.getenv("RATINGS_HOSTNAME") == null ? "ratings" : System.getenv("RATINGS_HOSTNAME");
    private final static String ratings_service = "http://" + ratings_hostname + services_domain + ":9080/ratings";
    // HTTP headers to propagate for distributed tracing are documented at
    // https://istio.io/docs/tasks/telemetry/distributed-tracing/overview/#trace-context-propagation
    private final static String[] headers_to_proagate = {"x-request-id","x-b3-traceid","x-b3-spanid","x-b3-sampled","x-b3-flags",
      "x-ot-span-context","x-datadog-trace-id","x-datadog-parent-id","x-datadog-sampled", "end-user","user-agent"};

    private String getJsonResponse (String productId, int starsReviewer1, int starsReviewer2) {
    	String result = "{";
    	result += "\"id\": \"" + productId + "\",";
    	result += "\"reviews\": [";

    	// reviewer 1:
    	result += "{";
    	result += "  \"reviewer\": \"Reviewer1\",";
    	result += "  \"text\": \"An extremely entertaining play by Shakespeare. The slapstick humour is refreshing!\"";
      if (ratings_enabled) {
        if (starsReviewer1 != -1) {
          result += ", \"rating\": {\"stars\": " + starsReviewer1 + ", \"color\": \"" + star_color + "\"}";
        }
        else {
          result += ", \"rating\": {\"error\": \"Ratings service is currently unavailable\"}";
        }
      }
    	result += "},";
    	
    	// reviewer 2:
    	result += "{";
    	result += "  \"reviewer\": \"Reviewer2\",";
    	result += "  \"text\": \"Absolutely fun and entertaining. The play lacks thematic depth when compared to other plays by Shakespeare.\"";
      if (ratings_enabled) {
        if (starsReviewer2 != -1) {
          result += ", \"rating\": {\"stars\": " + starsReviewer2 + ", \"color\": \"" + star_color + "\"}";
        }
        else {
          result += ", \"rating\": {\"error\": \"Ratings service is currently unavailable\"}";
        }
      }
    	result += "}";
    	
    	result += "]";
    	result += "}";

    	return result;
    }
    
    private JsonObject getRatings(String productId, HttpHeaders requestHeaders) {
      ClientBuilder cb = ClientBuilder.newBuilder();
      Integer timeout = star_color.equals("black") ? 10000 : 2500;
      cb.property("com.ibm.ws.jaxrs.client.connection.timeout", timeout);
      cb.property("com.ibm.ws.jaxrs.client.receive.timeout", timeout);
      Client client = cb.build();
      String uri = ratings_service + "/" + productId;
      WebTarget ratingsTarget = client.target(uri);
      Invocation.Builder builder = ratingsTarget.request(MediaType.APPLICATION_JSON);
      for (String header : headers_to_proagate) {
        String value = requestHeaders.getHeaderString(header);
        if (value != null) {
          builder.header(header,value);
        }
      }
      try {
        log("INFO", requestHeaders, "Calling GET %s", uri);
        Response r = builder.get();

        int statusCode = r.getStatusInfo().getStatusCode();
        if (statusCode == Response.Status.OK.getStatusCode()) {
          log("INFO", requestHeaders, "Ratings service return 200");
          try (StringReader stringReader = new StringReader(r.readEntity(String.class));
               JsonReader jsonReader = Json.createReader(stringReader)) {
            return jsonReader.readObject();
          }
        } else {
          log("ERROR", requestHeaders, "Unable to contact %s got status of %s", ratings_service, String.valueOf(statusCode));
          return null;
        }
      } catch (ProcessingException e) {
        log("ERROR", requestHeaders, "Unable to contact %s got exception " + e, ratings_service);
        return null;
      }
    }

    @GET
    @Path("/health")
    public Response health() {
        return Response.ok().type(MediaType.APPLICATION_JSON).entity("{\"status\": \"Reviews is healthy\"}").build();
    }

    @GET
    @Path("/reviews/{productId}")
    public Response bookReviewsById(@PathParam("productId") int productId, @Context HttpHeaders headers) {
      log("INFO", headers, "Finding reviews from product %s", String.valueOf(productId));
      int starsReviewer1 = -1;
      int starsReviewer2 = -1;

      if (ratings_enabled) {
        JsonObject ratingsResponse = getRatings(Integer.toString(productId), headers);
        if (ratingsResponse != null) {
          if (ratingsResponse.containsKey("ratings")) {
            JsonObject ratings = ratingsResponse.getJsonObject("ratings");
            if (ratings.containsKey("Reviewer1")){
          	  starsReviewer1 = ratings.getInt("Reviewer1");
            }
            if (ratings.containsKey("Reviewer2")){
              starsReviewer2 = ratings.getInt("Reviewer2");
            }
          }
        }
      } else {
        log("WARN", headers, "Ratings disabled");
        StringWriter sw = new StringWriter();
        final NullPointerException ex = new NullPointerException();
        ex.printStackTrace(new PrintWriter(sw));
        log("ERROR", headers, sw.toString());
        throw ex;
      }

      String jsonResStr = getJsonResponse(Integer.toString(productId), starsReviewer1, starsReviewer2);
      return Response.ok().type(MediaType.APPLICATION_JSON).entity(jsonResStr).build();
    }

    private void log(String level, HttpHeaders requestHeaders, String logText, String... params) {
      final String logLevel = String.format("[%s]", level);
      final String logTimestamp = String.format("[%s]", LocalDateTime.now());

      final String logService = String.format("[%s]", "reviews");
      final String traceId = requestHeaders.getHeaderString("x-b3-traceid");
      final String spanId = requestHeaders.getHeaderString("x-b3-spanid");
      final String logTracing = String.format("[reviews,%s,%s]", traceId, spanId);

      final String logClass = String.format("[%s]", this.getClass().getSimpleName());

      final String log = logLevel + logTimestamp + logService + logTracing + logClass + ": " + String.format(logText, params);
      if ("ERROR".equals(level)) {
        System.err.println(log);
      } else {
        System.out.println(log);
      }
    }
}
