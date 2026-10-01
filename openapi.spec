openapi: 3.0.0
info:
  title: EpsonConnect V2 API Specification
  version: v2.0
  description: "**1. Overview**  \nThe Epson Connect API (hereafter referred to as \"API\") provides a way to control and execute printing and other functions externally to devices connected to Epson Connect.<br>To use this service, you must register your device (printer or scanner) with Epson Connect.<br>Click <a href=\"https://developer.epsonconnect.com/portals/compatibleModels\" target=\"_blank\">here</a> to check compatible models.<br>Click <a href=\"https://www.epsonconnect.com/guide/en/html/p01.htm\" target=\"_blank\">here</a> learn how to register device (printer or scanner).\n\n**2. Glossary**  \n|Term|Description|\n| ---- | ---- |\n|Epson Connect|Epson Connect is a service that connects customers to Epson printers and scanners over the internet.|\n|Device|A printer or scanner connected to Epson Connect.|\n|Authorization Server|This is a server for obtaining access tokens.<br>If your device (printer or scanner) is not registered, you will be redirected to \"error=not_registered\" when authenticating your device.<br>It complies with RFC 6749 (The OAuth 2.0 Authorization Framework).<br>Please revoke the access token when a user unsubscribes from your service.|\n|Device Token|An access token that is acquired in the authorization code flow.<br>It is used for Bearer Authentication of the API operating the device.|\n|Refresh Token|A refresh token that is acquired in the authorization code flow.<br>It is used to refresh the device token.<br>When the device token is refreshed, a new refresh token is also issued.<br>The expire is 30 days.|\n|Application Token|An access token that is retrieved from the client credentials flow.<br>It is used for Bearer Authentication of the API that is not operating the device.|\n|Printing Job ID|An ID that identifies the print job.|\n|Scheduled print job ID|An ID that identifies the scheduled print job.|\n\n**3. Common Error List**  \n|Error string|Status code\t|Description|\n|----------|---------------|----|\n|invalid_resource|400|Invalid resource content|\n|not_supported|400|Does not support printing or scanning functions|\n|unauthorized|401|Device token or application token is invalid.|\n|internal_server_error|500|An unexpected error occurred|\n|not_registered|-|Device (printer or scanner) is not registered in Epson Connect.|\n"
servers:
  - url: 'https://api.epsonconnect.com/api/2'
    description: API server
  - url: 'https://dummy-api.epsonconnect.com/api/2'
    description: Demo server
tags:
  - name: auth
    description: Certification
  - name: device
    description: Device
  - name: printing
    description: Immediate printing
  - name: schedule printing
    description: Schedule printing
  - name: scanning
    description: Scanning
components:
  securitySchemes:
    deviceToken:
      type: oauth2
      description: Get a device token according to the authorization code flow
      x-default-scopes: device
      flows:
        authorizationCode:
          authorizationUrl: 'https://auth.epsonconnect.com/auth/authorize'
          tokenUrl: 'https://auth.epsonconnect.com/auth/token'
          scopes:
            device: device
    applicationToken:
      type: oauth2
      description: Get an application token according to the authorization code flow
      flows:
        clientCredentials:
          tokenUrl: 'https://auth.epsonconnect.com/auth/token'
    apiKey:
      type: apiKey
      name: x-api-key
      in: header
      description: Please set the API Key issued when creating the application.
  schemas:
    jobId: &ref_0
      type: string
      description: Printing job ID
    scheduleJobId: &ref_1
      type: string
      description: Scheduled print job ID
    destinationId: &ref_2
      type: string
      description: Scan Destination ID
    jobName: &ref_20
      type: string
      description: >
        Name to identify the printing job (1 to 256 characters, such as the file
        name to be printed)
    aliasName: &ref_41
      type: string
      description: Panel display name (1 to 20 characters)
    destination: &ref_43
      type: string
      description: Destination (4 to 544 characters)
    notification: &ref_5
      type: boolean
      description: |
        With or without notification<br>
        &nbsp;&nbsp;true ・・・With notification<br>
        &nbsp;&nbsp;false ・・・Without notification
    error: &ref_4
      type: object
      properties:
        error:
          type: string
          description: Error string
    type: &ref_42
      type: string
      enum:
        - url
        - mail
      description: |
        Scan destination services<br>
        &nbsp;&nbsp;url ・・・URL<br>
        &nbsp;&nbsp;mail ・・・Email address<br>
    printDateTime: &ref_36
      type: string
      description: >
        Printing reservation date and time (UTC)<br>

        &nbsp;&nbsp;The date and time can be specified from 15 minutes to 14
        days from the current time, and the number of minutes can be specified
        in 15-minute intervals of "00", "15", "30", and "45".<br>

        &nbsp;&nbsp;Format is "YYYYYMMDDHHMM"
    paperSize: &ref_10
      type: string
      enum:
        - ps_a3
        - ps_a4
        - ps_a5
        - ps_a6
        - ps_b5
        - ps_tabloid
        - ps_letter
        - ps_legal
        - ps_halfletter
        - ps_kg
        - ps_l
        - ps_2l
        - ps_10x12
        - ps_8x10
        - ps_hivision
        - ps_5x8
        - ps_postcard
      description: >
        Printable paper size([See Appendix
        B](https://docs.epsonconnect.com/en/api_appendix.html#appendixB))
    paperType: &ref_11
      type: string
      enum:
        - pt_plainpaper
        - pt_photopaper
        - pt_hagaki
        - pt_hagakiphoto
        - pt_hagakiinkjet
        - pt_roll
      description: >
        Printable stamp types([See Appendix
        C](https://docs.epsonconnect.com/en/api_appendix.html#appendixC))
    paperSource: &ref_14
      type: string
      enum:
        - auto
        - rear
        - front1
        - front2
        - front3
        - front4
        - roll
      description: >
        Paper feed device for printing([See Appendix
        D](https://docs.epsonconnect.com/en/api_appendix.html#appendixD))
    printQuality: &ref_13
      type: string
      enum:
        - high
        - normal
        - draft
      description: >
        Print quality when printing([See Appendix
        E](https://docs.epsonconnect.com/en/api_appendix.html#appendixE))
    doubleSided: &ref_16
      type: string
      enum:
        - none
        - long
        - short
      description: >
        Duplex printing([See Appendix
        F](https://docs.epsonconnect.com/en/api_appendix.html#appendixF))
    colorMode: &ref_15
      type: string
      enum:
        - color
        - mono
      description: >
        Color mode([See Appendix
        H](https://docs.epsonconnect.com/en/api_appendix.html#appendixH))
    status: &ref_7
      type: string
      enum:
        - preparing
        - reserved
        - pending
        - processing
        - media_empty
        - media_jam
        - marker_supply_empty
        - stopped_other
        - canceled
        - error_occurred
        - completed
        - expired
      description: >
        Printing job status([See Appendix
        I](https://docs.epsonconnect.com/en/api_appendix.html#appendixI))
    printMode: &ref_9
      type: string
      enum:
        - document
        - photo
      description: >
        Printing mode([See Appendix
        A](https://docs.epsonconnect.com/en/api_appendix.html#appendixJ))
    printType: &ref_6
      type: string
      enum:
        - ImmediatePrint
        - SchedulePrint
      description: >
        Printing type([See Appendix
        J](https://docs.epsonconnect.com/en/api_appendix.html#appendixK))
    borderless: &ref_12
      type: boolean
      description: |
        With or without edge at printing<br>
        &nbsp;&nbsp;true・・・Edgeless printing<br>
        &nbsp;&nbsp;false・・・Edge printing
    reverseOrder: &ref_17
      type: boolean
      description: |
        Reverse printing<br>
        &nbsp;&nbsp;true・・・Print from last page<br>
        &nbsp;&nbsp;false・・・Print from the first page<br>
    copies: &ref_18
      type: integer
      description: |
        Number of copies printed<br>
        &nbsp;&nbsp;Printable from 1 to 99 copies<br>
    collate: &ref_19
      type: boolean
      description: |
        Block printing<br>
        &nbsp;&nbsp;true・・・Part unit<br>
        &nbsp;&nbsp;false・・・Page unit<br>
    uploadFile: &ref_3
      type: object
      properties:
        File:
          type: string
          format: binary
  parameters:
    jobId: &ref_33
      in: path
      name: jobId
      required: true
      schema: *ref_0
      description: Printing job ID
      example:
        jobId: 886ba15084e744c98d9913786bbaf1ac
    scheduleId: &ref_39
      in: path
      name: scheduleJobId
      required: true
      schema: *ref_1
      description: Scheduled print job ID
      example:
        scheduleJobId: d318caa88966442faaee090f858aef35
    destinationId: &ref_46
      in: path
      name: destinationId
      required: true
      schema: *ref_2
      description: Scan Destination ID
      example:
        destinationId: 1328bbfbc48a43e3bf300607e6293a77
    file: &ref_22
      in: query
      name: File
      required: true
      schema:
        type: string
      description: >
        File extension to upload<br>

        Set using the following format: "1.(extension)"<br>

        Example for PDF files:<br>

        "1.pdf"<br>

        See Printable files ([Appendix
        G](https://docs.epsonconnect.com/en/api_appendix.html#appendixG)) for
        the file extensions that can be uploaded.
      example:
        File: 1.jpg
  requestBodies:
    File: &ref_23
      content:
        application/octet-stream:
          schema: *ref_3
        application/pdf:
          schema: *ref_3
        image/jpeg:
          schema: *ref_3
        image/png:
          schema: *ref_3
  responses:
    uploadBadRequest: &ref_24
      description: Bad Request<br>&nbsp;&nbsp;Request content is incorrect
    uploadNotFound: &ref_25
      description: Not Found<br>&nbsp;&nbsp;There is no print job
    schedulrUploadNotFound: &ref_37
      description: Not Found<br>&nbsp;&nbsp;Scheduled print job does not exist
    uploadMethodNotAllowed: &ref_26
      description: Method Not Allowed<br>&nbsp;&nbsp;HTTP method is incorrect
    uploadUnsupportedMediaType: &ref_29
      description: >-
        Unsupported Media Type<br>&nbsp;&nbsp;The specified file is not
        supported
    uploadConflict: &ref_27
      description: >-
        Conflict<br>&nbsp;&nbsp;A file with the same name has already been
        uploaded
    uploadPayloadTooLarge: &ref_28
      description: >
        Payload Too Large<br>

        &nbsp;&nbsp;The file size being uploaded or the number of files exceeds
        the maximum
    uploadInternalServerError: &ref_30
      description: Internal Server Error<br>&nbsp;&nbsp;An unexpected error occurred
    deviceNotFound: &ref_8
      description: |
        Cannot find the specified device
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
                description: Error string
            example:
              error: device_not_found
    deviceJobNotFound: &ref_32
      description: |
        Cannot find the specified device<br>
        Cannot find the specified print job
      content:
        application/json:
          schema: *ref_4
          examples:
            responses1:
              summary: Cannot find the specified device
              value:
                error: device_not_found
            responses2:
              summary: Cannot find the specified print job
              value:
                error: job_not_found
    jobLimitExceeded: &ref_35
      description: The number of print jobs waiting to be printed exceeds the maximum.
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
                description: Error string
            example:
              error: job_limit_exceeded
    deviceOrScheduleNotFound: &ref_38
      description: |
        Cannot find the specified device<br>
        Cannot find the specified scheduled print job
      content:
        application/json:
          schema: *ref_4
          examples:
            responses1:
              summary: Cannot find the specified device
              value:
                error: device_not_found
            responses2:
              summary: Cannot find the specified scheduled print job
              value:
                error: schedule_not_found
    commandNotAllowedOrScheduleLimitExceeded: &ref_40
      description: |
        Print reservation date/time is out of valid range<br>
        The maximum number of scheduled events has been exceeded
      content:
        application/json:
          schema: *ref_4
          examples:
            responses1:
              summary: Print reservation date/time is out of valid range
              value:
                error: command_not_allowed
            responses2:
              summary: The maximum number of scheduled events has been exceeded
              value:
                error: schedule_limit_exceeded
    deviceOrDestinationNotFound: &ref_47
      description: |
        Cannot find the specified device<br>
        Cannot find the specified scan destination
      content:
        application/json:
          schema: *ref_4
          examples:
            responses1:
              summary: Cannot find the specified device
              value:
                error: device_not_found
            responses2:
              summary: Cannot find the specified scan destination
              value:
                error: destination_not_found
    invalidPrintDataOrPrintSettings: &ref_31
      description: |
        The uploaded file is incorrect<br>
        The device does not support the specified print settings<br>
      content:
        application/json:
          schema: *ref_4
          examples:
            responses1:
              summary: The uploaded file is incorrect
              value:
                error: invalid_print_data
            responses2:
              summary: The device does not support the specified print settings
              value:
                error: invalid_print_settings
    invalidPrintData: &ref_34
      description: |
        The uploaded file is incorrect
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
                description: Error string
            example:
              error: invalid_print_data
    invalidPrintSettings: &ref_21
      description: |
        The device does not support the specified print settings.
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
                description: Error string
            example:
              error: invalid_print_settings
    duplicateAlias: &ref_44
      description: The panel display name is already in use
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
                description: Error string
            example:
              error: duplicate_alias_name
    destinationLimitExceeded: &ref_45
      description: >-
        The maximum number of scan destinations that can be registered has been
        exceeded
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
                description: Error string
            example:
              error: destination_limit_exceeded
paths:
  /printing/settings/notification:
    get:
      security:
        - applicationToken: []
          apiKey: []
      tags:
        - printing
      summary: Get Notification Information
      description: |
        Gets information about the specified device.<br>
        This API uses Bearer Authentication with a device token.
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  notification: *ref_5
                  callbackUri:
                    type: string
                    description: URI to receive notifications
                example:
                  notification: true
                  callbackUri: 'http://example.com'
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/printing/settings/notification' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("GET", "/api/2/printing/settings/notification",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/settings/notification",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/settings/notification")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/settings/notification",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
    post:
      security:
        - applicationToken: []
          apiKey: []
      tags:
        - printing
      summary: Notification Information Settings
      description: >
        Specifies settings for receiving changes in the status of print
        jobs.<br>

        This API uses Bearer Authentication with an application token.<br>

        Notifications are sent at the following times:<br>
          ・When printing is paused (out of paper, paper jam, or out of ink).<br>
          ・When a print job ends (successfully, cancellation, or error)<br>
          ・When a print job is deleted due to expiration
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - notification
              properties:
                notification: *ref_5
                callbackUri:
                  type: string
                  description: |
                    URI to receive notifications<br>
                    Specify from 11 to 2048 characters<br>
              example:
                notification: true
                callbackUri: 'http://example.com'
      responses:
        '204':
          description: Completed normally
      callbacks:
        notification:
          '{$request.body#/callbackUri}':
            post:
              requestBody:
                content:
                  application/json:
                    schema:
                      type: object
                      properties:
                        Param:
                          type: object
                          description: Object storing print status
                          properties:
                            Type: *ref_6
                            JobId:
                              type: string
                              description: Subsystem job ID
                            JobStatus: *ref_7
                            UpdateDate:
                              type: string
                              description: >
                                Printing job status update date and time
                                (UTC)<br>

                                Format is "YYYY/MM/DD HH:MM:SS"
                      example:
                        Param:
                          Type: ImmediatePrint
                          JobId: d318caa88966442faaee090f858aef35
                          JobStatus: pending
                          UpdateDate: '2021/08/06 06:42:13'
              responses:
                '200':
                  description: ''
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/printing/settings/notification' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"notification":true,"callbackUri":"http://example.com"}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"notification\":true,\"callbackUri\":\"http://example.com\"}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("POST", "/api/2/printing/settings/notification",
            payload, headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/settings/notification",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_POSTFIELDS => "{\"notification\":true,\"callbackUri\":\"http://example.com\"}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"notification\":true,\"callbackUri\":\"http://example.com\"}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/settings/notification")
              .post(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/settings/notification",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"notification\":true,\"callbackUri\":\"http://example.com\"}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /printing/devices/info:
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Get Device Information
      description: |
        Gets information about the specified device.<br>
        This API uses Bearer Authentication with a device token.
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  productName:
                    type: string
                    description: Product name of device
                  serialNumber:
                    type: string
                    description: Serial No. of device
                  multiByteDisplay:
                    type: boolean
                    description: >
                      Multibyte Character Usage (Panel display name for scan
                      destination)<br>

                      &nbsp;&nbsp;true・・・Allowed<br>

                      &nbsp;&nbsp;false・・・Not allowed
                  connected:
                    type: boolean
                    description: |
                      Epson Connect connection information for the device<br>
                      &nbsp;&nbsp;true・・・Connected <br>
                      &nbsp;&nbsp;false・・・Disconnected 
                example:
                  productName: DummyPrinter
                  serialNumber: ABCDE12345
                  multiByteDisplay: false
                  connected: true
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/printing/devices/info' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: |-
            import http.client

            conn = http.client.HTTPSConnection("api.epsonconnect.com")

            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }

            conn.request("GET", "/api/2/printing/devices/info", headers=headers)

            res = conn.getresponse()
            data = res.read()

            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/devices/info",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/devices/info")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/devices/info",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/printing/capability/{printMode}':
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Get Printing Capacity
      description: |
        Gets the printing capacity of the specified device.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - in: path
          required: true
          name: printMode
          description: >-
            Printing mode ([See Appendix
            A](https://docs.epsonconnect.com/en/api_appendix.html#appendixA))
          schema: *ref_9
          example:
            printMode: document
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  colorModes:
                    type: array
                    items:
                      type: string
                      enum:
                        - color
                        - mono
                    description: >
                      Array containing printable color modes<br>

                      Color mode ([See Appendix
                      H](https://docs.epsonconnect.com/en/api_appendix.html#appendixH))
                  resolutions:
                    type: array
                    items:
                      type: integer
                    description: |
                      Array containing output resolution
                  paperSizes:
                    description: >-
                      Array containing printing capacity objects for each paper
                      size
                    type: array
                    items:
                      type: object
                      properties:
                        paperSize: *ref_10
                        paperTypes:
                          type: array
                          description: >-
                            Array that allows printing capability objects for
                            each paper type
                          items:
                            type: object
                            properties:
                              paperType: *ref_11
                              borderless: *ref_12
                              paperSources:
                                type: array
                                description: >
                                  Array containing specifiable paper sources<br>

                                  Paper feed device for printing ([See Appendix
                                  D](https://docs.epsonconnect.com/en/api_appendix.html#appendixD))
                                items:
                                  type: string
                                  enum:
                                    - auto
                                    - rear
                                    - front1
                                    - front2
                                    - front3
                                    - front4
                                    - roll
                              printQualities:
                                description: >
                                  Array containing the print qualities that can
                                  be specified<br>

                                  Print quality when printing ([See Appendix
                                  E](https://docs.epsonconnect.com/en/api_appendix.html#appendixE))
                                type: array
                                items:
                                  type: string
                                  enum:
                                    - high
                                    - normal
                                    - draft
                              doubleSided:
                                description: >
                                  Duplex printing support<br>

                                  &nbsp;&nbsp;true・・・Duplex printing
                                  available<br>

                                  &nbsp;&nbsp;false・・・Duplex printing not
                                  available
                                type: boolean
                example:
                  colorModes:
                    - color
                    - mono
                  resolutions:
                    - 300
                    - 600
                  paperSizes:
                    - paperSize: ps_legal
                      paperTypes:
                        - paperType: pt_plainpaper
                          borderless: false
                          paperSources:
                            - front2
                          printQualities:
                            - normal
                            - high
                          doubleSided: false
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/printing/capability/document' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("GET", "/api/2/printing/capability/document",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/capability/document",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/capability/document")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/capability/document",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /printing/capability/default:
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Get Default Print Settings
      description: |
        Gets the default print settings for the specified device.<br>
        This API uses Bearer Authentication with a device token.
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  printSettings:
                    type: object
                    properties:
                      paperSize: *ref_10
                      paperType: *ref_11
                      borderless: *ref_12
                      printQuality: *ref_13
                      paperSource: *ref_14
                      colorMode: *ref_15
                      doubleSided: *ref_16
                      reverseOrder: *ref_17
                      copies: *ref_18
                      collate: *ref_19
                example:
                  printSettings:
                    paperSize: ps_legal
                    paperType: pt_plainpaper
                    borderless: false
                    printQuality: normal
                    paperSource: front2
                    colorMode: color
                    doubleSided: none
                    reverseOrder: false
                    copies: 1
                    collate: true
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/printing/capability/default' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("GET", "/api/2/printing/capability/default",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/capability/default",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/capability/default")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/capability/default",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /printing/jobs:
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Create Printing Job
      description: >
        Configures the print settings and issues the print job ID and file
        upload URI.<br>

        Please specify the values according to the print settings obtained from
        the Get Print Capability API.<br>

        The print job will expire after 3 days.<br>

        This API uses Bearer Authentication with a device token.
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - jobName
                - printMode
              properties:
                jobName: *ref_20
                printMode: *ref_9
                printSettings:
                  description: >
                    Object containing print settings<br>

                    If not specified, default print settings defined in Epson
                    Connect will be applied.<br>
                  type: object
                  required:
                    - paperSize
                    - paperType
                    - borderless
                    - printQuality
                    - paperSource
                    - colorMode
                  properties:
                    paperSize: *ref_10
                    paperType: *ref_11
                    borderless: *ref_12
                    printQuality: *ref_13
                    paperSource: *ref_14
                    colorMode: *ref_15
                    doubleSided:
                      allOf:
                        - *ref_16
                      default: none
                    reverseOrder:
                      allOf:
                        - *ref_17
                      default: true
                    copies:
                      allOf:
                        - *ref_18
                      default: 1
                    collate:
                      allOf:
                        - *ref_19
                      default: false
              example:
                jobName: sample
                printMode: document
                printSettings:
                  paperSize: ps_a4
                  paperType: pt_plainpaper
                  borderless: false
                  printQuality: normal
                  paperSource: front2
                  colorMode: mono
                  doubleSided: none
                  reverseOrder: false
                  copies: 1
                  collate: true
      responses:
        '201':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  jobId: *ref_0
                  uploadUri:
                    type: string
                    description: URI to upload files to be printed
                    format: uri
                example:
                  jobId: 886ba15084e744c98d9913786bbaf1ac
                  uploadUri: 'https://example.com/data?Key=uploadkey'
        '400': *ref_21
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/printing/jobs' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"jobName":"sample","printMode":"document","printSettings":{"paperSize":"ps_a4","paperType":"pt_plainpaper","borderless":false,"printQuality":"normal","paperSource":"front2","colorMode":"mono","doubleSided":"none","reverseOrder":false,"copies":1,"collate":true}}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"jobName\":\"sample\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("POST", "/api/2/printing/jobs", payload, headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/jobs",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_POSTFIELDS => "{\"jobName\":\"sample\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"jobName\":\"sample\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/jobs")
              .post(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/jobs",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"jobName\":\"sample\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /data:
    servers:
      - url: 'https://upload.epsonconnect.com'
    post:
      tags:
        - printing
      summary: File upload
      description: |
        Upload the file to be printed.<br>
        The file size limit is 20MB.
      parameters:
        - in: query
          name: Key
          schema:
            type: string
          required: true
          description: Upload key
          example:
            Key: 0f2b03323c91517ef779261c996e2c4a0bea16362c5de628e610d623b5b1fd29
        - *ref_22
      requestBody: *ref_23
      responses:
        '200':
          description: Completed normally
        '400': *ref_24
        '404': *ref_25
        '405': *ref_26
        '409': *ref_27
        '413': *ref_28
        '415': *ref_29
        '500': *ref_30
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://upload.epsonconnect.com/data?Key=0f2b03323c91517ef779261c996e2c4a0bea16362c5de628e610d623b5b1fd29&File=1.jpg'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("upload.epsonconnect.com")


            conn.request("POST",
            "/data?Key=0f2b03323c91517ef779261c996e2c4a0bea16362c5de628e610d623b5b1fd29&File=1.jpg")


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://upload.epsonconnect.com/data?Key=0f2b03323c91517ef779261c996e2c4a0bea16362c5de628e610d623b5b1fd29&File=1.jpg",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://upload.epsonconnect.com/data?Key=0f2b03323c91517ef779261c996e2c4a0bea16362c5de628e610d623b5b1fd29&File=1.jpg")
              .post(null)
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://upload.epsonconnect.com/data?Key=0f2b03323c91517ef779261c996e2c4a0bea16362c5de628e610d623b5b1fd29&File=1.jpg",
              "method": "POST",
              "headers": {}
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /printing/jobs/copy:
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Duplicate Print Job
      description: >
        Duplicates the print job and issues a new print job ID.<br>

        If you specify print settings, you can change only the specified print
        settings from the settings of the original print job.<br>

        This API uses Bearer Authentication with a device token.
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - fromJobId
              properties:
                fromJobId:
                  type: string
                  description: |
                    Copy source printing job ID
                jobName: *ref_20
                printSettings:
                  type: object
                  description: |
                    Object that stores print settings<br>
                  properties:
                    paperSize: *ref_10
                    paperType: *ref_11
                    borderless: *ref_12
                    printQuality: *ref_13
                    paperSource: *ref_14
                    colorMode: *ref_15
                    doubleSided: *ref_16
                    reverseOrder: *ref_17
                    copies: *ref_18
                    collate: *ref_19
              example:
                fromJobId: 886ba15084e744c98d9913786bbaf1ac
                jobName: sample
                printSettings:
                  paperSize: ps_a4
                  paperType: pt_plainpaper
                  borderless: false
                  printQuality: normal
                  paperSource: front2
                  colorMode: mono
                  doubleSided: none
                  reverseOrder: false
                  copies: 1
                  collate: true
      responses:
        '201':
          description: |
            Completed normally
          content:
            application/json:
              schema:
                properties:
                  jobId: *ref_0
                example:
                  jobId: 3cc7e49c9bfaf78c1f864353ccba1dd6
        '400': *ref_31
        '404': *ref_32
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/printing/jobs/copy' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"fromJobId":"886ba15084e744c98d9913786bbaf1ac","jobName":"sample","printSettings":{"paperSize":"ps_a4","paperType":"pt_plainpaper","borderless":false,"printQuality":"normal","paperSource":"front2","colorMode":"mono","doubleSided":"none","reverseOrder":false,"copies":1,"collate":true}}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"fromJobId\":\"886ba15084e744c98d9913786bbaf1ac\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("POST", "/api/2/printing/jobs/copy", payload, headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/jobs/copy",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_POSTFIELDS => "{\"fromJobId\":\"886ba15084e744c98d9913786bbaf1ac\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"fromJobId\":\"886ba15084e744c98d9913786bbaf1ac\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/jobs/copy")
              .post(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/jobs/copy",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"fromJobId\":\"886ba15084e744c98d9913786bbaf1ac\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/printing/jobs/{jobId}/print':
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Printing
      description: |
        Starts printing for the specified print job.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_33
      responses:
        '202':
          description: Completed normally
        '400': *ref_34
        '403': *ref_35
        '404': *ref_32
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/print' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("POST",
            "/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/print",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/print",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/print")
              .post(null)
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/print",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/printing/jobs/{jobId}/cancel':
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Cancel Printing
      description: |
        Cancels printing for the specified print job.<br>
        You cannot cancel a job that the printer has started printing.<br>
        If you need to do so, cancel printing on the printer itself.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_33
      responses:
        '204':
          description: Completed normally
        '403':
          description: Cannot be canceled in the current print job state
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
                    description: Error string
                example:
                  error: operation_not_allowed
        '404': *ref_32
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/cancel' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("POST",
            "/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/cancel",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/cancel",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/cancel")
              .post(null)
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac/cancel",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/printing/jobs/{jobId}':
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - printing
      summary: Get Print Job Information
      description: |
        Gets information about the specified print job.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_33
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: *ref_7
                  jobName: *ref_20
                  totalPages:
                    type: integer
                    description: >
                      If the printing job status is completed, "Number of pages
                      in print file multiplied by number of copies"<br>

                      0 if the printing job status is other than print completed
                  startDate:
                    type: string
                    format: date
                    description: |
                      Print execution time (UTC)
                  updateDate:
                    type: string
                    format: date
                    description: |
                      Printing job status update date and time (UTC)
                example:
                  status: completed
                  jobName: sample
                  totalPages: 1
                  startDate: '2021-08-06 02:00:45'
                  updateDate: '2021-08-06 02:01:26'
        '404': *ref_32
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("GET",
            "/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/printing/jobs/886ba15084e744c98d9913786bbaf1ac",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /scheduling/schedules:
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - schedule printing
      summary: Get Schedule Print Job List
      description: |
        Gets a list of reserved scheduled print jobs.<br>
        This API uses Bearer Authentication with a device token.
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  schedules:
                    type: array
                    description: Object containing schedule
                    items:
                      properties:
                        scheduleJobId: *ref_1
                        jobName: *ref_20
                        printDateTime: *ref_36
                        printMode: *ref_9
                        printSettings:
                          description: |
                            Object containing printing settings
                          type: object
                          properties:
                            paperSize: *ref_10
                            paperType: *ref_11
                            borderless: *ref_12
                            printQuality: *ref_13
                            paperSource: *ref_14
                            colorMode: *ref_15
                            doubleSided: *ref_16
                            reverseOrder: *ref_17
                            copies: *ref_18
                            collate: *ref_19
                example:
                  schedules:
                    - scheduleJobId: d318caa88966442faaee090f858aef35
                      jobName: sample
                      printDateTime: '202404011230'
                      printMode: document
                      printSettings:
                        paperSize: ps_a4
                        paperType: pt_plainpaper
                        borderless: false
                        printQuality: normal
                        paperSource: front2
                        colorMode: mono
                        doubleSided: none
                        reverseOrder: false
                        copies: 1
                        collate: true
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/scheduling/schedules' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: |-
            import http.client

            conn = http.client.HTTPSConnection("api.epsonconnect.com")

            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }

            conn.request("GET", "/api/2/scheduling/schedules", headers=headers)

            res = conn.getresponse()
            data = res.read()

            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scheduling/schedules",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scheduling/schedules")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scheduling/schedules",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - schedule printing
      summary: Create Schedule Printing Job
      description: >
        Configures the print settings and issues the scheduled print job ID and
        file upload URI.<br>

        Schedule Printing creates a print job at the specified
        printDateTime.<br>

        This does not guarantee that printing will start at the specified
        time.<br>

        This API uses Bearer Authentication with a device token.
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - jobName
                - printDateTime
                - printMode
              properties:
                jobName: *ref_20
                printDateTime: *ref_36
                printMode: *ref_9
                printSettings:
                  description: |
                    An object that stores print settings.
                  type: object
                  required:
                    - paperSize
                    - paperType
                    - borderless
                    - printQuality
                    - paperSource
                    - colorMode
                  properties:
                    paperSize: *ref_10
                    paperType: *ref_11
                    borderless: *ref_12
                    printQuality: *ref_13
                    paperSource: *ref_14
                    colorMode: *ref_15
                    doubleSided:
                      allOf:
                        - *ref_16
                      default: none
                    reverseOrder:
                      allOf:
                        - *ref_17
                      default: true
                    copies:
                      allOf:
                        - *ref_18
                      default: 1
                    collate:
                      allOf:
                        - *ref_19
                      default: false
              example:
                jobName: sample
                printDateTime: '202404011230'
                printMode: document
                printSettings:
                  paperSize: ps_a4
                  paperType: pt_plainpaper
                  borderless: false
                  printQuality: normal
                  paperSource: front2
                  colorMode: mono
                  doubleSided: none
                  reverseOrder: false
                  copies: 1
                  collate: true
      responses:
        '201':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  scheduleJobId: *ref_1
                  uploadUri:
                    type: string
                    description: URI to upload files to be printed
                    format: uri
                example:
                  scheduleJobId: d318caa88966442faaee090f858aef35
                  uploadUri: 'https://example.com/data?Key=uploadkey'
        '400': *ref_21
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/scheduling/schedules' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"jobName":"sample","printDateTime":"202404011230","printMode":"document","printSettings":{"paperSize":"ps_a4","paperType":"pt_plainpaper","borderless":false,"printQuality":"normal","paperSource":"front2","colorMode":"mono","doubleSided":"none","reverseOrder":false,"copies":1,"collate":true}}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"jobName\":\"sample\",\"printDateTime\":\"202404011230\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("POST", "/api/2/scheduling/schedules", payload,
            headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scheduling/schedules",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_POSTFIELDS => "{\"jobName\":\"sample\",\"printDateTime\":\"202404011230\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"jobName\":\"sample\",\"printDateTime\":\"202404011230\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scheduling/schedules")
              .post(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scheduling/schedules",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"jobName\":\"sample\",\"printDateTime\":\"202404011230\",\"printMode\":\"document\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /schedule_data:
    servers:
      - url: 'https://upload.epsonconnect.com'
    post:
      tags:
        - schedule printing
      summary: Schedule Print File Upload
      description: |
        Uploads the file to be used for scheduled printing.<br>
        The file size limit is 20MB.
      parameters:
        - in: query
          name: Key
          schema:
            type: string
          required: true
          description: Scheduled print job ID
          example:
            Key: d318caa88966442faaee090f858aef35
        - *ref_22
      requestBody: *ref_23
      responses:
        '200':
          description: Completed normally
        '400': *ref_24
        '404': *ref_37
        '413': *ref_28
        '500': *ref_30
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://upload.epsonconnect.com/schedule_data?Key=d318caa88966442faaee090f858aef35&File=1.jpg'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("upload.epsonconnect.com")


            conn.request("POST",
            "/schedule_data?Key=d318caa88966442faaee090f858aef35&File=1.jpg")


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://upload.epsonconnect.com/schedule_data?Key=d318caa88966442faaee090f858aef35&File=1.jpg",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://upload.epsonconnect.com/schedule_data?Key=d318caa88966442faaee090f858aef35&File=1.jpg")
              .post(null)
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://upload.epsonconnect.com/schedule_data?Key=d318caa88966442faaee090f858aef35&File=1.jpg",
              "method": "POST",
              "headers": {}
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /scheduling/schedules/copy:
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - schedule printing
      summary: Duplicate Schedule Print Job
      description: >
        Duplicates the scheduled print job and issues a new scheduled print job
        ID.<br>

        If you specify print settings, you can change only the specified print
        settings from the settings of the copy source schedule print job.<br>

        This API uses Bearer Authentication with a device token.
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - fromScheduleJobId
              properties:
                fromScheduleJobId:
                  type: string
                  description: |
                    Copy source Scheduled print job ID
                printDateTime: *ref_36
                jobName: *ref_20
                printSettings:
                  type: object
                  description: |
                    Object containing print settings<br>
                  properties:
                    paperSize: *ref_10
                    paperType: *ref_11
                    borderless: *ref_12
                    printQuality: *ref_13
                    paperSource: *ref_14
                    colorMode: *ref_15
                    doubleSided: *ref_16
                    reverseOrder: *ref_17
                    copies: *ref_18
                    collate: *ref_19
              example:
                fromScheduleJobId: d318caa88966442faaee090f858aef35
                printDateTime: '202404011230'
                jobName: sample
                printSettings:
                  paperSize: ps_a4
                  paperType: pt_plainpaper
                  borderless: false
                  printQuality: normal
                  paperSource: front2
                  colorMode: mono
                  doubleSided: none
                  reverseOrder: false
                  copies: 1
                  collate: true
      responses:
        '201':
          description: |
            Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  scheduleJobId: *ref_0
                example:
                  scheduleJobId: 97d2ddb296730d1ffc02e37c901e26d1
        '400': *ref_31
        '404': *ref_38
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/scheduling/schedules/copy' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"fromScheduleJobId":"d318caa88966442faaee090f858aef35","printDateTime":"202404011230","jobName":"sample","printSettings":{"paperSize":"ps_a4","paperType":"pt_plainpaper","borderless":false,"printQuality":"normal","paperSource":"front2","colorMode":"mono","doubleSided":"none","reverseOrder":false,"copies":1,"collate":true}}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"fromScheduleJobId\":\"d318caa88966442faaee090f858aef35\",\"printDateTime\":\"202404011230\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("POST", "/api/2/scheduling/schedules/copy", payload,
            headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scheduling/schedules/copy",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_POSTFIELDS => "{\"fromScheduleJobId\":\"d318caa88966442faaee090f858aef35\",\"printDateTime\":\"202404011230\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"fromScheduleJobId\":\"d318caa88966442faaee090f858aef35\",\"printDateTime\":\"202404011230\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scheduling/schedules/copy")
              .post(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scheduling/schedules/copy",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"fromScheduleJobId\":\"d318caa88966442faaee090f858aef35\",\"printDateTime\":\"202404011230\",\"jobName\":\"sample\",\"printSettings\":{\"paperSize\":\"ps_a4\",\"paperType\":\"pt_plainpaper\",\"borderless\":false,\"printQuality\":\"normal\",\"paperSource\":\"front2\",\"colorMode\":\"mono\",\"doubleSided\":\"none\",\"reverseOrder\":false,\"copies\":1,\"collate\":true}}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/scheduling/schedules/{scheduleJobId}/reserve':
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - schedule printing
      summary: Reserve Schedule Printing Job
      description: |
        Schedules printing for the specified print job.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_39
      responses:
        '202':
          description: Completed normally
        '400': *ref_34
        '403': *ref_40
        '404': *ref_38
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35/reserve' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("POST",
            "/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35/reserve",
            headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35/reserve",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35/reserve")
              .post(null)
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35/reserve",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/scheduling/schedules/{scheduleJobId}':
    delete:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - schedule printing
      summary: Delete Scheduled Print Job
      description: |
        Deletes the specified scheduled print job.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_39
      responses:
        '204':
          description: Completed normally
        '403':
          description: |
            The reservation deadline has been exceeded
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
                    description: Error string
                example:
                  error: command_not_allowed
        '404': *ref_38
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request DELETE \
              --url 'https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("DELETE",
            "/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35", headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "DELETE",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35")
              .delete(null)
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35",
              "method": "DELETE",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - schedule printing
      summary: Get Scheduled Print Job Information
      description: |
        Gets information about the specified scheduled print job.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_39
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: *ref_7
                  jobName: *ref_20
                  totalPages:
                    type: integer
                    description: >
                      If the printing job status is completed, "Number of pages
                      in print file multiplied by number of copies"<br>

                      0 if the printing job status is other than print completed
                  startDate:
                    type: string
                    format: date
                    description: |
                      Print execution time (UTC)
                  updateDate:
                    type: string
                    format: date
                    description: |
                      Printing job status update date and time (UTC)
                example:
                  status: completed
                  jobName: sample
                  totalPages: 1
                  startDate: '2021-08-06 02:00:45'
                  updateDate: '2021-08-06 02:01:26'
        '404': *ref_38
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("GET",
            "/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35", headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scheduling/schedules/d318caa88966442faaee090f858aef35",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  /scanning/destinations:
    get:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - scanning
      summary: Get Scan Destination List
      description: |
        Gets a list of scan destinations registered to the device.<br>
        This API uses Bearer Authentication with a device token.
      responses:
        '200':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  destinations:
                    type: array
                    description: Array containing the scan destination object
                    items:
                      type: object
                      properties:
                        destinationId: *ref_2
                        aliasName: *ref_41
                        destinationService: *ref_42
                        destination: *ref_43
                example:
                  destinations:
                    - destinationId: 9fc3c45a34d249c9b09b180a6a118503
                      aliasName: mail_sample
                      destinationService: mail
                      destination: epsonconnectapi@example.com
                    - destinationId: 1328bbfbc48a43e3bf300607e6293a77
                      aliasName: url_sample
                      destinationService: url
                      destination: 'http://example.com'
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request GET \
              --url 'https://api.epsonconnect.com/api/2/scanning/destinations' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: |-
            import http.client

            conn = http.client.HTTPSConnection("api.epsonconnect.com")

            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }

            conn.request("GET", "/api/2/scanning/destinations", headers=headers)

            res = conn.getresponse()
            data = res.read()

            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scanning/destinations",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "GET",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scanning/destinations")
              .get()
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scanning/destinations",
              "method": "GET",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
    post:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - scanning
      summary: Register Scan Destination
      description: >
        Registers scan destinations.<br>

        This API uses Bearer Authentication with a device token.

        A receiver program is required when specifying a URL as a scanned
        destination.<br>


        **Scan data format**<br>

        Scan data will be sent to the scan destination of the specified URL in
        the following format.<br>


        **a. HTTP method**<br>

        POST<br>


        **b. HTTP header**<br>

        |Header name|Required|Value|

        | ---- | ---- | ---- |

        |Content-Type|○|multipart format, delimiters<br>multipart/form-data;
        boundary= -----------MultipartPost|


        **c. Query string**<br>

        None<br>


        **d. HTTP body**<br>

        Send file data is specified.<br>

        In the multipart format, the file-specific HTTP headers
        "Content-Disposition", "Content-Type" and the file data are specified
        with delimiters.<br>

        A blank line is used to identify the HTTP header and file data. A line
        feed code is CR (0x0D) + LF (0x0A).<br>

        ```

        -------------MultipartPost

        Content-Disposition: form-data; Key(serial number); filename=File Name

        Content-Type: image/jpeg(application/pdf)


        File Data(Hexadecimal String)

        -------------MultipartPost

        Content-Disposition: form-data; Key(serial number); filename=File Name

        Content-Type: image/jpeg(application/pdf)


        File Data(Hexadecimal String)

        -------------MultipartPost--
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - aliasName
                - destinationService
                - destination
              properties:
                aliasName: *ref_41
                destinationService: *ref_42
                destination: *ref_43
              example:
                aliasName: mail_sample
                destinationService: mail
                destination: epsonconnectapi@example.com
      responses:
        '201':
          description: Completed normally
          content:
            application/json:
              schema:
                type: object
                properties:
                  destinationId: *ref_2
                example:
                  destinationId: 1328bbfbc48a43e3bf300607e6293a77
        '400': *ref_44
        '403': *ref_45
        '404': *ref_8
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request POST \
              --url 'https://api.epsonconnect.com/api/2/scanning/destinations' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"aliasName":"mail_sample","destinationService":"mail","destination":"epsonconnectapi@example.com"}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"aliasName\":\"mail_sample\",\"destinationService\":\"mail\",\"destination\":\"epsonconnectapi@example.com\"}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("POST", "/api/2/scanning/destinations", payload,
            headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scanning/destinations",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "POST",
              CURLOPT_POSTFIELDS => "{\"aliasName\":\"mail_sample\",\"destinationService\":\"mail\",\"destination\":\"epsonconnectapi@example.com\"}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"aliasName\":\"mail_sample\",\"destinationService\":\"mail\",\"destination\":\"epsonconnectapi@example.com\"}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scanning/destinations")
              .post(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scanning/destinations",
              "method": "POST",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"aliasName\":\"mail_sample\",\"destinationService\":\"mail\",\"destination\":\"epsonconnectapi@example.com\"}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
  '/scanning/destinations/{destinationId}':
    put:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - scanning
      summary: Update Scan Destination
      description: |
        Updates the scan destination.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_46
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - aliasName
                - destination
              properties:
                aliasName: *ref_41
                destination: *ref_43
              example:
                aliasName: mail_sample
                destination: epsonconnect@example.com
      responses:
        '204':
          description: Completed normally
        '400': *ref_44
        '404': *ref_47
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request PUT \
              --url 'https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB' \
              --header 'content-type: application/json' \
              --data '{"aliasName":"mail_sample","destination":"epsonconnect@example.com"}'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            payload =
            "{\"aliasName\":\"mail_sample\",\"destination\":\"epsonconnect@example.com\"}"


            headers = {
                'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                'content-type': "application/json"
            }

            conn.request("PUT",
            "/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77", payload,
            headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "PUT",
              CURLOPT_POSTFIELDS => "{\"aliasName\":\"mail_sample\",\"destination\":\"epsonconnect@example.com\"}",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type: application/json"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: >-
            OkHttpClient client = new OkHttpClient();


            MediaType mediaType = MediaType.parse("application/json");

            RequestBody body = RequestBody.create(mediaType,
            "{\"aliasName\":\"mail_sample\",\"destination\":\"epsonconnect@example.com\"}");

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77")
              .put(body)
              .addHeader("content-type", "application/json")
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77",
              "method": "PUT",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB",
                "content-type": "application/json"
              }
              "processData": false,
              "data": "{\"aliasName\":\"mail_sample\",\"destination\":\"epsonconnect@example.com\"}"
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
    delete:
      security:
        - deviceToken: []
          apiKey: []
      tags:
        - scanning
      summary: Delete Scan Destination
      description: |
        Deletes the scan destination.<br>
        This API uses Bearer Authentication with a device token.
      parameters:
        - *ref_46
      responses:
        '204':
          description: Completed normally
        '404': *ref_47
      x-codeSamples:
        - lang: Shell
          source: |-
            curl --request DELETE \
              --url 'https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77' \
              --header 'Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I' \
              --header 'x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB'
        - lang: Python
          source: >-
            import http.client


            conn = http.client.HTTPSConnection("api.epsonconnect.com")


            headers = {
              'Authorization': "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
              'x-api-key': "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
            }


            conn.request("DELETE",
            "/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77", headers=headers)


            res = conn.getresponse()

            data = res.read()


            print(data.decode("utf-8"))
        - lang: PHP
          source: |-
            <?php

            $curl = curl_init();

            curl_setopt_array($curl, [
              CURLOPT_URL => "https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77",
              CURLOPT_RETURNTRANSFER => true,
              CURLOPT_ENCODING => "",
              CURLOPT_MAXREDIRS => 10,
              CURLOPT_TIMEOUT => 30,
              CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
              CURLOPT_CUSTOMREQUEST => "DELETE",
              CURLOPT_HTTPHEADER => [
                "Authorization: Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key: MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              ],
            ]);

            $response = curl_exec($curl);
            $err = curl_error($curl);

            curl_close($curl);

            if ($err) {
              echo "cURL Error #:" . $err;
            } else {
              echo $response;
            }
        - lang: Java
          source: |-
            OkHttpClient client = new OkHttpClient();

            Request request = new Request.Builder()
              .url("https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77")
              .delete(null)
              .addHeader("Authorization", "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I")
              .addHeader("x-api-key", "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB")
              .build();

            Response response = client.newCall(request).execute();
        - lang: Javascript
          source: |-
            const settings = {
              "async": true,
              "crossDomain": true,
              "url": "https://api.epsonconnect.com/api/2/scanning/destinations/1328bbfbc48a43e3bf300607e6293a77",
              "method": "DELETE",
              "headers": {
                "Authorization": "Bearer B-Tcytwjnm9818P9mb3V9lsnHFMHki3FeDgsOFQSu_I",
                "x-api-key": "MGTNVvnVmmFbYasgApRtuXC7t8EDMcRxDRvMZTZB"
              }
            };

            $.ajax(settings).done(function (response) {
              console.log(response);
            });
