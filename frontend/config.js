// ============================================================
// CareConnect frontend configuration
// ============================================================
// This is the ONE file you edit for the S3 + CloudFront frontend.
// It tells the web page which API endpoint to send patient questions to.
//
// >>> LEARNERS: replace the API_URL value below with YOUR OWN API Gateway URL.
//     Find it at: API Gateway > (your API) > Stages > prod > Invoke URL,
//     then add the /careconnect route at the end.
//
// After editing, upload this config.js (together with index.html and the
// assets/ folder) to your S3 website bucket, then invalidate the CloudFront
// cache so the new value is picked up.
// ============================================================

window.CARECONNECT_CONFIG = {
  // Your API Gateway invoke URL for the POST /careconnect route.
  API_URL: "https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod/careconnect"
};
