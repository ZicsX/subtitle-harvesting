import logging
import boto3


class S3SubtitleManager:
    def __init__(self, bucket_name):
        self.s3_client = boto3.client("s3")
        self.bucket_name = bucket_name

    def upload_subtitle(self, subtitle_filename, subtitle_content):
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=subtitle_filename,
                Body=subtitle_content,
                ContentType="text/plain",
            )
            logging.info(
                f"Uploaded {subtitle_filename} to S3 bucket {self.bucket_name}."
            )
        except Exception as e:
            logging.error(f"Error uploading {subtitle_filename} to S3: {e}")
