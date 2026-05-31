library(rmarkdown)

repo_dir <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)

evaluation_folder <- file.path(repo_dir, "evaluation")
evaluation_folder <- normalizePath(evaluation_folder, winslash = "/", mustWork = FALSE)

output_name <- "Benchmarking_Gaussian_Splatting.pdf"

rmarkdown::render(
  input = file.path(repo_dir, "src", "r_evaluation", "Benchmarking_Gaussian_Splatting.Rmd"),
  output_format = rmarkdown::pdf_document(latex_engine = "tectonic"),
  output_file = output_name,
  output_dir = evaluation_folder,
  params = list(folder = evaluation_folder)
)

browseURL(file.path(evaluation_folder, output_name))